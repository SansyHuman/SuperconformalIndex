from fractions import Fraction
from pathlib import Path
import shutil
import sys
import unittest


PROJECT_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from index.n2_theory_branches import (
    COULOMB_INDEX_RING,
    calculate_coulomb_branch_index,
    calculate_coulomb_branch_index_from_full_index,
    calculate_lagrangian_coulomb_branch_index,
    calculate_plethystic_exponential,
    coulomb_branch_spectrum_from_gauge_factors,
)
from index.n2_theory_index import _to_sage_polynomial
from anomalies.check_n2_anomalies import GaugeFactorData
from anomalies.lie_algebra import get_lie_algebra


HAS_FORM = shutil.which("form") is not None


@unittest.skipUnless(HAS_FORM, "FORM is required")
class CoulombBranchPlethysticTests(unittest.TestCase):
    def test_su3_spectrum(self):
        result = calculate_coulomb_branch_index([2, 3], 8)
        x = COULOMB_INDEX_RING.gen()
        expected = (
            1
            + x**2
            + x**3
            + x**4
            + x**5
            + 2 * x**6
            + x**7
            + 2 * x**8
        )
        self.assertEqual(result, expected)

    def test_fractional_non_lagrangian_dimension(self):
        result = calculate_coulomb_branch_index(
            [Fraction(6, 5)], Fraction(18, 5)
        )
        x = COULOMB_INDEX_RING.gen()
        self.assertEqual(
            result,
            1 + x ** Fraction(6, 5) + x ** Fraction(12, 5) + x ** Fraction(18, 5),
        )

    def test_spectrum_multiplicity_mapping(self):
        result = calculate_coulomb_branch_index({2: 2}, 6)
        x = COULOMB_INDEX_RING.gen()
        self.assertEqual(result, 1 + 2 * x**2 + 3 * x**4 + 4 * x**6)

    def test_signed_plethystic_log_supports_relations(self):
        result = calculate_plethystic_exponential({2: 2, 4: -1}, 8)
        x = COULOMB_INDEX_RING.gen()
        self.assertEqual(
            result,
            1 + 2 * x**2 + 2 * x**4 + 2 * x**6 + 2 * x**8,
        )


class CoulombLimitFromFullIndexTests(unittest.TestCase):
    @staticmethod
    def _full_index():
        return _to_sage_polynomial(
            {
                (0, 0, 0): Fraction(1),
                (4, 0, 4): Fraction(1),
                (4, 0, -2): Fraction(36),
                (5, 1, 2): Fraction(-1),
                (5, -1, 2): Fraction(-1),
                (6, 0, 6): Fraction(1),
                (6, 0, 0): Fraction(-36),
                (6, 0, -3): Fraction(40),
            }
        )

    def test_extracts_coulomb_ray_from_sage_full_index(self):
        result = calculate_coulomb_branch_index(full_index=self._full_index())
        x = COULOMB_INDEX_RING.gen()
        self.assertEqual(result, 1 + x**2 + x**3)

    def test_accepts_serialized_full_index(self):
        result = calculate_coulomb_branch_index(
            full_index=str(self._full_index()),
            max_dimension=2,
        )
        x = COULOMB_INDEX_RING.gen()
        self.assertEqual(result, 1 + x**2)

    def test_rejects_y_dependence_on_coulomb_ray(self):
        invalid = _to_sage_polynomial({(2, 1, 2): Fraction(1)})
        with self.assertRaisesRegex(ValueError, "independent of y"):
            calculate_coulomb_branch_index_from_full_index(invalid)

    def test_rejects_divergent_coulomb_limit(self):
        invalid = _to_sage_polynomial({(2, 0, 4): Fraction(1)})
        with self.assertRaisesRegex(ValueError, "diverges"):
            calculate_coulomb_branch_index_from_full_index(invalid)


@unittest.skipUnless(HAS_FORM, "FORM is required")
class LagrangianCoulombBranchTests(unittest.TestCase):
    @staticmethod
    def _factor(factor_id, cartan_type):
        return GaugeFactorData(factor_id, get_lie_algebra(cartan_type))

    def test_single_gauge_factor_is_accepted(self):
        factor = self._factor("gauge", "A2")
        result = calculate_lagrangian_coulomb_branch_index(factor, 6)
        x = COULOMB_INDEX_RING.gen()
        self.assertEqual(
            result,
            1 + x**2 + x**3 + x**4 + x**5 + 2 * x**6,
        )

    def test_product_gauge_factors_preserve_degree_multiplicity(self):
        factors = (
            self._factor("left", "A1"),
            self._factor("right", "A2"),
        )
        self.assertEqual(
            coulomb_branch_spectrum_from_gauge_factors(factors),
            (2, 2, 3),
        )

        result = calculate_lagrangian_coulomb_branch_index(factors, 6)
        x = COULOMB_INDEX_RING.gen()
        self.assertEqual(
            result,
            1 + 2 * x**2 + x**3 + 3 * x**4 + 2 * x**5 + 5 * x**6,
        )

    def test_invariant_degrees_cover_every_supported_family(self):
        expected = {
            "A3": (2, 3, 4),
            "B3": (2, 4, 6),
            "C3": (2, 4, 6),
            "D4": (2, 4, 4, 6),
            "E6": (2, 5, 6, 8, 9, 12),
            "E7": (2, 6, 8, 10, 12, 14, 18),
            "E8": (2, 8, 12, 14, 18, 20, 24, 30),
            "F4": (2, 6, 8, 12),
            "G2": (2, 6),
        }
        for cartan_type, degrees in expected.items():
            with self.subTest(cartan_type=cartan_type):
                factor = self._factor("gauge", cartan_type)
                self.assertEqual(
                    coulomb_branch_spectrum_from_gauge_factors(factor),
                    degrees,
                )

    def test_rejects_non_gauge_factor_data(self):
        with self.assertRaisesRegex(ValueError, "GaugeFactorData"):
            calculate_lagrangian_coulomb_branch_index(["A2"], 6)


class CoulombBranchValidationTests(unittest.TestCase):
    def test_low_cutoff_does_not_invoke_form(self):
        self.assertEqual(
            calculate_coulomb_branch_index(
                [2], 1, form_executable="missing-form-for-test"
            ),
            1,
        )

    def test_requires_exactly_one_source(self):
        with self.assertRaisesRegex(ValueError, "exactly one"):
            calculate_coulomb_branch_index(max_dimension=4)
        with self.assertRaisesRegex(ValueError, "exactly one"):
            calculate_coulomb_branch_index(
                [2], 4, full_index=self._full_index_for_validation()
            )

    @staticmethod
    def _full_index_for_validation():
        return _to_sage_polynomial({(0, 0, 0): Fraction(1)})

    def test_spectrum_requires_max_dimension(self):
        with self.assertRaisesRegex(ValueError, "max_dimension"):
            calculate_coulomb_branch_index([2])

    def test_rejects_negative_spectrum_multiplicity(self):
        with self.assertRaisesRegex(ValueError, "nonnegative"):
            calculate_coulomb_branch_index({2: -1}, 4)

    def test_rejects_inexact_float_dimensions(self):
        with self.assertRaisesRegex(ValueError, "exact"):
            calculate_coulomb_branch_index([1.2], 4)


if __name__ == "__main__":
    unittest.main()
