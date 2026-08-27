from fractions import Fraction
from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from anomalies import check_n2_anomalies as checker
from anomalies.lie_algebra import (
    conjugate_dynkin_labels,
    dynkin_index as lie_dynkin_index,
    get_lie_algebra,
    named_representation_labels,
    quadratic_casimir as lie_quadratic_casimir,
    representation_dimension as lie_representation_dimension,
    representation_reality as lie_representation_reality,
)


class CheckerTests(unittest.TestCase):
    def test_backend_uses_sage_root_and_character_objects(self):
        algebra = get_lie_algebra("E6")
        self.assertEqual(str(algebra.sage_cartan_type), "['E', 6]")
        self.assertTrue(type(algebra.root_system).__module__.startswith("sage."))
        self.assertTrue(type(algebra.character_ring).__module__.startswith("sage."))
        self.assertEqual(
            conjugate_dynkin_labels("E6", (1, 0, 0, 0, 0, 0)),
            (0, 0, 0, 0, 0, 1),
        )

    def test_symplectic_group_uses_sp_rank_convention(self):
        algebra = get_lie_algebra("C3")
        self.assertEqual(algebra.group, "Sp(3)")
        result = checker.check_simple_theory("C3", [])
        self.assertEqual(result["group"], "Sp(3)")

    def test_root_data_and_minimal_representations_for_every_family(self):
        expected = {
            # type: (dim(g), h_dual, dim(minimal), T(minimal), reality)
            "A4": (24, 5, 5, Fraction(1, 2), "complex"),
            "B3": (21, 5, 7, Fraction(1), "real"),
            "C3": (21, 4, 6, Fraction(1, 2), "pseudoreal"),
            "D5": (45, 8, 10, Fraction(1), "real"),
            "E6": (78, 12, 27, Fraction(3), "complex"),
            "E7": (133, 18, 56, Fraction(6), "pseudoreal"),
            "E8": (248, 30, 248, Fraction(30), "real"),
            "F4": (52, 9, 26, Fraction(3), "real"),
            "G2": (14, 4, 7, Fraction(1), "real"),
        }
        for cartan_type, values in expected.items():
            with self.subTest(cartan_type=cartan_type):
                dim_g, h_dual, dim_rep, index, reality = values
                algebra = get_lie_algebra(cartan_type)
                labels = named_representation_labels(algebra, "fundamental")
                self.assertEqual(algebra.dimension, dim_g)
                self.assertEqual(algebra.dual_coxeter_number, h_dual)
                self.assertEqual(
                    lie_representation_dimension(algebra, labels), dim_rep
                )
                self.assertEqual(lie_dynkin_index(algebra, labels), index)
                self.assertEqual(lie_representation_reality(algebra, labels), reality)

    def test_adjoint_normalization_for_every_simple_family(self):
        for cartan_type in ("A4", "B3", "C3", "D5", "E6", "E7", "E8", "F4", "G2"):
            with self.subTest(cartan_type=cartan_type):
                algebra = get_lie_algebra(cartan_type)
                labels = algebra.adjoint_labels
                self.assertEqual(
                    lie_representation_dimension(algebra, labels), algebra.dimension
                )
                self.assertEqual(
                    lie_quadratic_casimir(algebra, labels),
                    algebra.dual_coxeter_number,
                )
                self.assertEqual(
                    lie_dynkin_index(algebra, labels), algebra.dual_coxeter_number
                )

    def test_spinor_and_exceptional_reality_types(self):
        cases = (
            ("B2", "spinor", "pseudoreal"),
            ("D5", "spinor", "complex"),
            ("D6", "spinor", "pseudoreal"),
            ("E6", "fundamental", "complex"),
            ("E7", "fundamental", "pseudoreal"),
            ("F4", "fundamental", "real"),
            ("G2", "fundamental", "real"),
        )
        for cartan_type, name, expected in cases:
            with self.subTest(cartan_type=cartan_type, representation=name):
                labels = named_representation_labels(cartan_type, name)
                self.assertEqual(
                    lie_representation_reality(cartan_type, labels), expected
                )

    def test_less_common_half_hyper_data_matches_classification_tables(self):
        cases = (
            ("A5", [0, 0, 1, 0, 0], 20, Fraction(3)),
            ("C3", [0, 0, 1], 14, Fraction(5, 2)),
            ("D6", [0, 0, 0, 0, 1, 0], 32, Fraction(4)),
        )
        for cartan_type, labels, dimension, index in cases:
            with self.subTest(cartan_type=cartan_type):
                self.assertEqual(
                    lie_representation_dimension(cartan_type, labels), dimension
                )
                self.assertEqual(lie_dynkin_index(cartan_type, labels), index)
                self.assertEqual(
                    lie_representation_reality(cartan_type, labels), "pseudoreal"
                )

    def test_e6_four_fundamentals_are_one_loop_conformal(self):
        result = checker.check_simple_theory(
            "E6", [{"representation": "fundamental", "number": 4}]
        )
        self.assertTrue(result["anomaly_free"])
        self.assertEqual(result["matter_beta_contribution"], 24)
        self.assertEqual(result["b0"], 0)

    def test_c3_fundamental_half_hyper_has_witten_anomaly(self):
        one = checker.check_simple_theory(
            "C3", [{"representation": "fundamental", "kind": "half"}]
        )
        two = checker.check_simple_theory(
            "C3",
            [{"representation": "fundamental", "kind": "half", "number": 2}],
        )
        self.assertFalse(one["global_gauge_anomaly_free"])
        self.assertEqual(one["witten_anomaly_parity"], 1)
        self.assertTrue(two["anomaly_free"])

    def test_mixed_classical_exceptional_product_uses_spectator_dimensions(self):
        result = checker.check_product_theory(
            [{"id": "symplectic", "algebra": "C2"}, {"id": "g2", "algebra": "G2"}],
            [
                {
                    "representations": {
                        "symplectic": "fundamental",
                        "g2": "fundamental",
                    }
                }
            ],
        )
        factors = {factor["id"]: factor for factor in result["gauge_factors"]}
        self.assertEqual(factors["symplectic"]["matter_beta_contribution"], 7)
        self.assertEqual(factors["g2"]["matter_beta_contribution"], 8)
        self.assertEqual(factors["g2"]["b0"], 0)

    def test_general_single_factor_input_dispatch(self):
        result = checker.check_input_data(
            {
                "algebra": "E7",
                "hypermultiplets": [
                    {"representation": "fundamental", "number": 3}
                ],
            }
        )
        self.assertEqual(result["group"], "E7")
        self.assertTrue(result["lagrangian_scft_candidate"])

    def test_malformed_algebra_is_reported_as_a_value_error(self):
        with self.assertRaisesRegex(ValueError, "algebra must be"):
            checker.check_input_data({"algebra": ["E6"]})

    def test_symmetric_plus_antisymmetric_is_conformal(self):
        for n in range(2, 11):
            result = checker.check_simple_theory(
                f"A{n - 1}",
                [
                    {"representation": "symmetric", "number": 1},
                    {"representation": "antisymmetric", "number": 1},
                ],
            )
            self.assertTrue(result["anomaly_free"])
            self.assertEqual(result["b0"], 0)

    def test_su2_single_fundamental_half_has_witten_anomaly(self):
        result = checker.check_simple_theory(
            "A1",
            [{"representation": "fundamental", "number": 1, "kind": "half"}],
        )
        self.assertTrue(result["perturbative_gauge_anomaly_free"])
        self.assertFalse(result["global_gauge_anomaly_free"])
        self.assertFalse(result["anomaly_free"])

    def test_su2_two_fundamental_halves_are_witten_safe(self):
        result = checker.check_simple_theory(
            "A1",
            [{"representation": "fundamental", "number": 2, "kind": "half"}],
        )
        self.assertTrue(result["anomaly_free"])

    def test_half_hyper_in_complex_rep_is_rejected(self):
        result = checker.check_simple_theory(
            "A4",
            [{"representation": "fundamental", "number": 1, "kind": "half"}],
        )
        self.assertFalse(result["anomaly_free"])
        self.assertTrue(result["errors"])

    def test_common_indices(self):
        n = 7
        cartan_type = f"A{n - 1}"
        symmetric = named_representation_labels(cartan_type, "symmetric")
        antisymmetric = named_representation_labels(cartan_type, "antisymmetric")
        adjoint = named_representation_labels(cartan_type, "adjoint")
        self.assertEqual(
            lie_dynkin_index(cartan_type, symmetric), Fraction(n + 2, 2)
        )
        self.assertEqual(
            lie_dynkin_index(cartan_type, antisymmetric), Fraction(n - 2, 2)
        )
        self.assertEqual(lie_dynkin_index(cartan_type, adjoint), n)

    def test_removed_n_schema_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "needs algebra or gauge_groups"):
            checker.check_input_data({"N": 5})

    def test_bifundamental_spectator_dimensions_enter_each_beta_function(self):
        result = checker.check_product_theory(
            [{"id": "left", "algebra": "A1"}, {"id": "right", "algebra": "A2"}],
            [
                {
                    "representations": {
                        "left": "fundamental",
                        "right": "fundamental",
                    }
                }
            ],
        )
        factors = {factor["id"]: factor for factor in result["gauge_factors"]}
        self.assertEqual(factors["left"]["matter_beta_contribution"], 3)
        self.assertEqual(factors["right"]["matter_beta_contribution"], 2)

    def test_two_su2_bifundamentals_are_conformal(self):
        result = checker.check_product_theory(
            [{"id": "left", "algebra": "A1"}, {"id": "right", "algebra": "A1"}],
            [
                {
                    "name": "bifundamental",
                    "representations": {
                        "left": "fundamental",
                        "right": "fundamental",
                    },
                    "number": 2,
                }
            ],
        )
        self.assertTrue(result["anomaly_free"])
        self.assertTrue(result["one_loop_beta_vanishes"])
        self.assertTrue(result["lagrangian_scft_candidate"])

    def test_su2_trifundamental_half_hyper_is_witten_safe(self):
        groups = [{"id": name, "algebra": "A1"} for name in ("a", "b", "c")]
        result = checker.check_product_theory(
            groups,
            [
                {
                    "representations": {
                        "a": "fundamental",
                        "b": "fundamental",
                        "c": "fundamental",
                    },
                    "kind": "half",
                }
            ],
        )
        self.assertTrue(result["anomaly_free"])
        self.assertEqual(
            [factor["witten_anomaly_parity"] for factor in result["gauge_factors"]],
            [0, 0, 0],
        )

    def test_half_hyper_in_real_bifundamental_is_rejected(self):
        result = checker.check_product_theory(
            [{"id": "a", "algebra": "A1"}, {"id": "b", "algebra": "A1"}],
            [
                {
                    "representations": {
                        "a": "fundamental",
                        "b": "fundamental",
                    },
                    "kind": "half",
                }
            ],
        )
        self.assertFalse(result["anomaly_free"])
        self.assertIn("overall pseudoreal", result["errors"][0])


if __name__ == "__main__":
    unittest.main()
