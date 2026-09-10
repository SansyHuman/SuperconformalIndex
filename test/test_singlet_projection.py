"""Check singlet contraction with exact weights and known tensor invariants."""
from collections import defaultdict
from pathlib import Path
from random import Random
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from index.char_decomposition_cache import CharacterDecompositionCache as Cache
from test.test_character_decomposition_cache import su2_fundamental_adams_product


def su3_weight_singlet(product):
    """Independent Weyl constant term, without character decomposition."""
    fundamental = {(1, 0): 1, (-1, 1): 1, (0, -1): 1}
    anti = {tuple(-x for x in weight): 1 for weight in fundamental}
    adjoint = defaultdict(int)
    for left in fundamental:
        for right in anti:
            adjoint[tuple(a + b for a, b in zip(left, right))] += 1
    adjoint[0, 0] -= 1
    weights = {(1, 0): fundamental, (0, 1): anti, (1, 1): adjoint}
    result = {(0, 0): 1}
    for labels, powers in product:
        for adams, exponent in enumerate(powers, start=1):
            for _ in range(exponent):
                updated = defaultdict(int)
                for left, a in result.items():
                    for right, b in weights[labels].items():
                        updated[tuple(x + adams * y for x, y in zip(left, right))] += a * b
                result = updated
    # Multiply by the Weyl denominator and extract its constant term.
    for root in ((2, -1), (-1, 2), (1, 1)):
        updated = defaultdict(int, result)
        for weight, coefficient in result.items():
            updated[tuple(x - y for x, y in zip(weight, root))] -= coefficient
        result = updated
    return result.get((0, 0), 0)


class SingletProjectionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)

    def cache(self, name='cache', workers=1):
        cache = Cache(self.directory / name, max_workers=workers)
        self.addCleanup(cache.close)
        return cache

    def test_complex_signed_pair_needs_no_tensor_decomposition(self):
        cache = self.cache()
        fundamental, anti = {(1, 0): 1}, {(0, 1): 1}
        left, right = {(1, 0): 2, (0, 1): -3}, {(1, 0): 5, (0, 1): 7}
        with patch.object(cache, '_run_lie', side_effect=AssertionError('unexpected LiE call')):
            self.assertEqual(cache.singlet_multiplicities('A2', 2, [
                [fundamental, fundamental], [fundamental, anti], [left, right],
                [{(1, 0): 10**100}, {(0, 1): -7}],
            ]), [0, 1, -1, -7 * 10**100])

    def test_pseudoreal_pair_has_positive_singlet(self):
        cache = self.cache()
        with patch.object(cache, '_run_lie', side_effect=AssertionError('unexpected LiE call')):
            self.assertEqual(cache.singlet_multiplicities('A1', 1, [
                [{(1,): 1}, {(1,): 1}],
            ]), [1])

    @unittest.skipUnless(shutil.which('lie'), 'LiE is required')
    def test_grouped_adams_factors_split_before_decomposition(self):
        cache = self.cache()
        adjoint = (1, 0, 0, 0, 0, 0, 0, 1)
        # psi_4(adj) * psi_5(adj): only the two atomic Adams operations are needed.
        with patch.object(cache, '_calculate_decomposition',
                          wraps=cache._calculate_decomposition) as calculate, \
                patch.object(cache, '_tensor_decompositions',
                             side_effect=AssertionError('decomposed the complete product')):
            self.assertEqual(cache.get_singlet_multiplicities('A8', 8, [
                [(adjoint, (0, 0, 0, 1, 1))],
            ]), [12])
        self.assertEqual(calculate.call_count, 2)
        self.assertTrue(all(sum(call.args[2]) == 1 for call in calculate.call_args_list))

    @unittest.skipUnless(shutil.which('lie'), 'LiE is required')
    def test_mixed_products_with_three_or_more_factors(self):
        cache = self.cache()
        f, anti = ((1, 0), (1,)), ((0, 1), (1,))
        products = [[f] * 3, [f, f, anti, anti], [f] * 3 + [anti] * 3]
        self.assertEqual(cache.get_singlet_multiplicities('A2', 2, products), [1, 2, 6])
        decomposed = [[{labels: 1} for labels, _ in product] for product in products]
        self.assertEqual(cache.singlet_multiplicities('A2', 2, decomposed), [1, 2, 6])

    @unittest.skipUnless(shutil.which('lie'), 'LiE is required')
    def test_adams_singlets_match_su2_weights_with_serial_and_parallel_workers(self):
        powers = [(a, b, c) for a in range(5) for b in range(4) for c in range(3)
                  if 0 < a + 2 * b + 3 * c <= 8]
        products = [[((1,), power)] for power in powers]
        expected = [su2_fundamental_adams_product(power).get((0,), 0) for power in powers]
        for workers in (1, 3):
            with self.subTest(workers=workers):
                self.assertEqual(self.cache(str(workers), workers).get_singlet_multiplicities(
                    'A1', 1, products), expected)

    @unittest.skipUnless(shutil.which('lie'), 'LiE is required')
    def test_mixed_adams_singlets_match_independent_su3_weights(self):
        rng = Random(9052026)
        products = [[]]
        for _ in range(30):
            product = []
            budget = 6
            for _ in range(rng.randrange(1, 5)):
                if not budget:
                    break
                adams = rng.randrange(1, min(3, budget) + 1)
                product.append((rng.choice([(1, 0), (0, 1), (1, 1)]),
                                (0,) * (adams - 1) + (1,)))
                budget -= adams
            products.append(product)
        self.assertEqual(self.cache().get_singlet_multiplicities('A2', 2, products),
                         [su3_weight_singlet(product) for product in products])

    def test_trivial_characters_and_zero_virtual_characters(self):
        cache = self.cache()
        with patch.object(cache, '_run_lie', side_effect=AssertionError('unexpected LiE call')):
            self.assertEqual(cache.get_singlet_multiplicities('A2', 2, [
                [], [((0, 0), (0, 3))], [((0, 0), (2, 0, 1))],
            ]), [1, 1, 1])
            self.assertEqual(cache.singlet_multiplicities('A2', 2, [
                [{(1, 0): 0}, {(0, 1): 1}], [{(0, 0): -5}, {(0, 0): 2}],
            ]), [0, -10])


if __name__ == '__main__':
    unittest.main(verbosity=2)
