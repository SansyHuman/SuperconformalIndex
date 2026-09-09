from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path
import sqlite3
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from index.char_decomposition_cache import CharacterDecompositionCache as Cache


def su2_fundamental_adams_product(powers):
    """Independent oracle: expand weights, then subtract adjacent weights."""
    weights = {0: 1}
    for adams, exponent in enumerate(powers, start=1):
        for _ in range(exponent):
            expanded = {}
            for weight, coefficient in weights.items():
                for shift in (-adams, adams):
                    expanded[weight + shift] = expanded.get(weight + shift, 0) + coefficient
            weights = expanded
    return {(weight,): weights.get(weight, 0) - weights.get(weight + 2, 0)
            for weight in range(max(weights) + 1)
            if weights.get(weight, 0) != weights.get(weight + 2, 0)}


def populate_shared_database(request):
    database_path, exponent = request
    with Cache(database_path=database_path, max_workers=1) as cache:
        decomposition = cache.get_decomposition('A1', (1,), (exponent,))
        singlet = cache.get_singlet_multiplicities('A1', 1, [[((1,), (exponent,))]])[0]
    return decomposition, singlet


@unittest.skipUnless(shutil.which("lie"), "LiE is required")
class SQLiteCacheTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

    def cache(self, name='new', **kwargs):
        cache = Cache(self.directory / name, **kwargs)
        self.addCleanup(cache.close)
        return cache

    def test_default_and_explicit_paths(self):
        self.assertEqual(Cache().database_path, ROOT / 'char_decomposition_cache.db')
        self.assertEqual(Cache(self.directory).database_path, self.directory / 'char_decomposition_cache.db')
        self.assertEqual(Cache(database_path=self.directory / 'custom.db').database_path,
                         self.directory / 'custom.db')
        with self.assertRaises(ValueError):
            Cache(self.directory, database_path=self.directory / 'other.db')

    def test_signed_decomposition_persists_and_returns_copies(self):
        cache = self.cache()
        self.assertEqual(cache.get_decomposition('A1', [1], [0, 1]), {(0,): -1, (2,): 1})
        cache.get_decomposition('A1', [1], [0, 1])[(0,)] = 999
        self.assertEqual(cache.get_decomposition('A1', [1], [0, 1])[(0,)], -1)
        cache.close()
        reopened = self.cache(lie_executable='missing-lie')
        self.assertEqual(reopened.get_decomposition('a_1', (1,), (0, 1, 0)), {(0,): -1, (2,): 1})
        with sqlite3.connect(cache.database_path) as connection:
            self.assertEqual(connection.execute('PRAGMA journal_mode').fetchone()[0], 'wal')
            self.assertEqual(connection.execute('PRAGMA integrity_check').fetchone()[0], 'ok')

    def test_arbitrary_size_coefficients_and_empty_decomposition(self):
        cache = self.cache()
        huge = -(10 ** 100)
        with patch.object(cache, '_calculate_decomposition', return_value={(0,): huge}):
            self.assertEqual(cache.get_decomposition('A1', (1,), (1,)), {(0,): huge})
        with patch.object(cache, '_calculate_decomposition', return_value={}):
            self.assertEqual(cache.get_decomposition('A1', (2,), (1,)), {})
        self.assertEqual(cache.singlet_multiplicities('A1', 1, [[{(0,): huge}]]), [huge])
        cache.close()
        reopened = self.cache(lie_executable='missing-lie')
        self.assertEqual(reopened.get_decomposition('A1', (1,), (1,)), {(0,): huge})
        self.assertEqual(reopened.get_decomposition('A1', (2,), (1,)), {})
        self.assertEqual(reopened.singlet_multiplicities('A1', 1, [[{(0,): huge}]]), [huge])

    def test_character_singlets_merge_repetitions_and_preserve_conjugates(self):
        cache = self.cache()
        f, anti = ((1, 0), (1,)), ((0, 1), (1,))
        products = [[f, anti], [anti, f], [f, f], [((1, 0), (2,))], [], [((1, 0), (0, 1))]]
        self.assertEqual(cache.get_singlet_multiplicities('A2', 2, products), [1, 1, 0, 0, 1, 0])
        with sqlite3.connect(cache.database_path) as connection:
            self.assertEqual(connection.execute('SELECT count(*) FROM singlet_coefficients').fetchone()[0], 4)

    def test_persisted_singlets_bypass_decompositions_completely(self):
        cache = self.cache()
        products = [[((1,), (0, 1))], [((1,), (1,))], []]
        expected = [-1, 0, 1]
        self.assertEqual(cache.get_singlet_multiplicities('A1', 1, products), expected)
        cache.close()
        with sqlite3.connect(cache.database_path) as connection:
            connection.execute('DELETE FROM character_decompositions')
        reopened = self.cache(lie_executable='missing-lie')
        with patch.object(reopened, 'get_decompositions', side_effect=AssertionError('decomposed on hit')):
            self.assertEqual(reopened.get_singlet_multiplicities('A1', 1, products), expected)

    def test_direct_decomposed_singlets_cache_zero_negative_and_reordered_products(self):
        cache = self.cache()
        products = [[], [{}], [{(0,): -5}], [{(1,): -1}, {(1,): 1}]]
        self.assertEqual(cache.singlet_multiplicities('A1', 1, products), [1, 0, -5, -1])
        cache.close()
        reopened = self.cache(lie_executable='missing-lie')
        products[-1].reverse()
        self.assertEqual(reopened.singlet_multiplicities('A1', 1, products), [1, 0, -5, -1])

    def test_group_is_part_of_singlet_key(self):
        cache = self.cache()
        products = [[((1, 0), (2,))]]
        self.assertEqual(cache.get_singlet_multiplicities('A2', 2, products), [0])
        self.assertEqual(cache.get_singlet_multiplicities('C2', 2, products), [1])

    def test_parallel_generation_matches_independent_weight_expansion(self):
        requests = [('A1', (1,), (0, 3)), ('A1', (1,), (1, 1, 1)), ('A1', (1,), (2, 0, 0, 1))]
        expected = [su2_fundamental_adams_product(request[2]) for request in requests]
        cache = self.cache(max_workers=3)
        self.assertEqual(cache.get_decompositions(requests), expected)
        cache.close()
        reopened = self.cache(lie_executable='missing-lie', max_workers=3)
        self.assertEqual(reopened.get_decompositions(requests), expected)

    def test_threads_share_file_and_client_without_lost_writes(self):
        cache = self.cache(max_workers=1)
        def calculate(n):
            try:
                return cache.get_decomposition('A1', (1,), (n,))
            finally:
                cache.close()
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(calculate, [1, 2, 3, 4] * 3))
        expected = [su2_fundamental_adams_product((n,)) for n in [1, 2, 3, 4] * 3]
        self.assertEqual(results, expected)
        with sqlite3.connect(cache.database_path) as connection:
            self.assertEqual(connection.execute('SELECT count(*) FROM character_decompositions').fetchone()[0], 4)
            self.assertEqual(connection.execute('PRAGMA integrity_check').fetchone()[0], 'ok')

    def test_failure_does_not_cache_a_false_zero(self):
        cache = self.cache(lie_executable='missing-lie')
        with self.assertRaises(RuntimeError):
            cache.get_singlet_multiplicities('A1', 1, [[((1,), (1,))]])
        with sqlite3.connect(cache.database_path) as connection:
            self.assertEqual(connection.execute('SELECT count(*) FROM singlet_coefficients').fetchone()[0], 0)

    def test_independent_processes_write_overlapping_cache_entries(self):
        path = self.directory / 'shared.db'
        exponents = [1, 2, 3, 4, 3, 2, 4, 1]
        with ProcessPoolExecutor(max_workers=3) as executor:
            results = list(executor.map(populate_shared_database, [(path, n) for n in exponents]))
        expected = [su2_fundamental_adams_product((n,)) for n in exponents]
        self.assertEqual(results, [(value, value.get((0,), 0)) for value in expected])
        with sqlite3.connect(path) as connection:
            self.assertEqual(connection.execute('SELECT count(*) FROM character_decompositions').fetchone()[0], 4)
            self.assertEqual(connection.execute('SELECT count(*) FROM singlet_coefficients').fetchone()[0], 4)
            self.assertEqual(connection.execute('PRAGMA integrity_check').fetchone()[0], 'ok')

    def test_rejects_incompatible_schema(self):
        path = self.directory / 'other.db'
        with sqlite3.connect(path) as connection:
            connection.execute('PRAGMA user_version=999')
        with Cache(database_path=path) as cache:
            with self.assertRaisesRegex(RuntimeError, 'schema version'):
                cache.get_decomposition('A1', (1,), (1,))

    def test_rejects_nonintegral_keys_and_wrong_rank(self):
        cache = self.cache()
        for request in [('A1', (1.5,), (1,)), ('A1', (1,), (1.5,)), ('A2', (1,), (1,))]:
            with self.subTest(request=request), self.assertRaises(ValueError):
                cache.get_decomposition(*request)
        with self.assertRaises(ValueError):
            cache.get_singlet_multiplicities('A2', 1, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
