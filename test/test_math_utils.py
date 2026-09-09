from itertools import product
from pathlib import Path
import random
import sys
import unittest


PROJECT_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from common.math_utils import frobenius_solve, frobenius_system_solve


class FrobeniusSystemTests(unittest.TestCase):
    def test_coupled_equations_with_zero_coefficients(self):
        self.assertCountEqual(
            frobenius_system_solve([[1, 0, 2], [0, 1, 3]], [4, 6]),
            [(4, 6, 0), (2, 3, 1), (0, 0, 2)],
        )

    def test_zero_rows_targets_and_empty_systems(self):
        for rows, targets, expected in (
            ([], [], [()]),
            ([[], []], [0, 0], [()]),
            ([[]], [1], []),
            ([[0, 0]], [1], []),
            ([[0, 0], [1, 1]], [0, 2], [(0, 2), (1, 1), (2, 0)]),
            ([[1, 0], [1, 1]], [0, 2], [(0, 2)]),
            ([[1, 1]], [0], [(0, 0)]),
            ([[1]], [-1], []),
            ([[1], [1]], [1, 2], []),
        ):
            with self.subTest(rows=rows, targets=targets):
                self.assertCountEqual(frobenius_system_solve(rows, targets), expected)

    def test_dependent_rows_do_not_duplicate_solutions(self):
        self.assertCountEqual(
            frobenius_system_solve([[1, 1], [2, 2]], [3, 6]),
            [(0, 3), (1, 2), (2, 1), (3, 0)],
        )

    def test_row_gcd_reduction_handles_large_exact_integers(self):
        large = 10**80
        self.assertCountEqual(
            frobenius_system_solve(
                [[large, 0, 2 * large], [0, 7, 21]], [4 * large, 42]
            ),
            [(4, 6, 0), (2, 3, 1), (0, 0, 2)],
        )
        self.assertEqual(frobenius_system_solve([[6, 10]], [7]), [])

    def test_huge_coefficients_of_fixed_zero_variables_are_omitted(self):
        self.assertEqual(
            frobenius_system_solve([[1, 0], [0, 1], [10**80, 1]], [0, 2, 2]),
            [(0, 2)],
        )
        with self.assertRaisesRegex(OverflowError, "int64"):
            frobenius_system_solve([[1]], [1 << 64])

    def test_rejects_invalid_shapes_negative_coefficients_and_free_variables(self):
        for rows, targets in (
            ([[1]], []),
            ([], [1]),
            ([[1, 2], [1]], [3, 1]),
            ([[1, -1]], [2]),
            ([[1, 0]], [2]),
            ([[0]], [0]),
        ):
            with self.subTest(rows=rows, targets=targets):
                with self.assertRaises(ValueError):
                    frobenius_system_solve(rows, targets)
        for rows, targets in (([[1.5]], [2]), ([[1]], [2.0]), ([["1"]], [2])):
            with self.subTest(rows=rows, targets=targets):
                with self.assertRaises(TypeError):
                    frobenius_system_solve(rows, targets)

    def test_accepts_one_shot_iterables_and_limits_solution_count(self):
        result = frobenius_system_solve(
            (iter(row) for row in [[1, 1], [2, 2]]), iter([9, 18]), max_solutions=3
        )
        self.assertEqual(len(result), 3)
        self.assertEqual(len(set(result)), 3)
        self.assertTrue(all(x + y == 9 for x, y in result))
        self.assertEqual(frobenius_system_solve([[1]], [1], max_solutions=0), [])
        with self.assertRaises(ValueError):
            frobenius_system_solve([[1]], [1], max_solutions=-1)
        with self.assertRaises(TypeError):
            frobenius_system_solve([[1]], [1], max_solutions=1.5)

    def test_single_equation_matches_existing_solver(self):
        for coefficients in ([], [1], [2, 3], [2, 2, 5], [4, 6], [100, 3]):
            for target in range(-1, 15):
                with self.subTest(coefficients=coefficients, target=target):
                    self.assertCountEqual(
                        frobenius_system_solve([coefficients], [target]),
                        frobenius_solve(coefficients, target),
                    )

    def test_matches_exhaustive_search_for_small_random_systems(self):
        rng = random.Random(20260909)
        for case in range(60):
            height, width = rng.randint(1, 4), rng.randint(1, 4)
            rows = [[rng.randrange(4) for _ in range(width)] for _ in range(height)]
            for j in range(width):
                if not any(row[j] for row in rows):
                    rows[0][j] = 1
            targets = [rng.randrange(9) for _ in rows]
            bounds = [
                min(b // row[j] for row, b in zip(rows, targets) if row[j])
                for j in range(width)
            ]
            expected = {
                counts for counts in product(*(range(bound + 1) for bound in bounds))
                if all(
                    sum(c * n for c, n in zip(row, counts)) == target
                    for row, target in zip(rows, targets)
                )
            }
            with self.subTest(case=case, rows=rows, targets=targets):
                actual = frobenius_system_solve(rows, targets)
                self.assertEqual(len(actual), len(set(actual)))
                self.assertEqual(set(actual), expected)


if __name__ == "__main__":
    unittest.main()
