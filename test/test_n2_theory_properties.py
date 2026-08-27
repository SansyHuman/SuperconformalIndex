from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from common import n2_theory_properties as properties


class TheoryPropertyTests(unittest.TestCase):
    def test_complex_conjugate_full_hypers_share_one_flavor_block(self):
        result = properties.calculate_n2_theory_properties(
            {
                "algebra": "A2",
                "hypermultiplets": [
                    {"representation": "fundamental", "number": 2},
                    {"representation": "antifundamental", "number": 4},
                ],
            }
        )
        self.assertTrue(result["lagrangian_scft_candidate"])
        self.assertEqual(result["flavor_symmetry"]["connected_group"], "U(6)")
        self.assertEqual(result["flavor_symmetry"]["dimension"], 36)
        self.assertEqual(result["conformal_manifold_dimension"], 1)

    def test_real_bifundamentals_have_symplectic_flavor(self):
        result = properties.calculate_n2_theory_properties(
            {
                "gauge_groups": [
                    {"id": "left", "algebra": "A1"},
                    {"id": "right", "algebra": "A1"},
                ],
                "hypermultiplets": [
                    {
                        "representations": {
                            "left": "fundamental",
                            "right": "fundamental",
                        },
                        "number": 2,
                    }
                ],
            }
        )
        self.assertTrue(result["lagrangian_scft_candidate"])
        self.assertEqual(
            result["flavor_symmetry"]["connected_group"], "Sp(2)"
        )
        self.assertEqual(result["conformal_manifold_dimension"], 2)
        self.assertEqual(
            result["exactly_marginal_gauge_couplings"], ["left", "right"]
        )

    def test_pseudoreal_product_counts_half_hyper_units(self):
        result = properties.calculate_n2_theory_properties(
            {
                "gauge_groups": [
                    {"id": "symplectic", "algebra": "C2"},
                    {"id": "g2", "algebra": "G2"},
                ],
                "hypermultiplets": [
                    {
                        "representations": {
                            "symplectic": "fundamental",
                            "g2": "fundamental",
                        },
                        "kind": "half",
                        "number": 2,
                    }
                ],
            }
        )
        factor = result["flavor_symmetry"]["factors"][0]
        self.assertEqual(result["flavor_symmetry"]["connected_group"], "SO(2)")
        self.assertEqual(factor["half_hyper_units"], 2)
        self.assertIsNone(result["conformal_manifold_dimension"])

    def test_single_trifundamental_has_no_continuous_flavor(self):
        result = properties.calculate_n2_theory_properties(
            {
                "gauge_groups": [
                    {"id": factor_id, "algebra": "A1"}
                    for factor_id in ("a", "b", "c")
                ],
                "hypermultiplets": [
                    {
                        "representations": {
                            "a": "fundamental",
                            "b": "fundamental",
                            "c": "fundamental",
                        },
                        "kind": "half",
                    }
                ],
            }
        )
        self.assertEqual(result["flavor_symmetry"]["connected_group"], "trivial")
        self.assertEqual(result["flavor_symmetry"]["factors"][0]["group"], "SO(1)")

    def test_existing_json_file_uses_same_input_schema(self):
        path = PROJECT_ROOT / "anomalies" / "example_e6.json"
        result = properties.calculate_n2_theory_properties_from_file(path)
        self.assertEqual(result["flavor_symmetry"]["connected_group"], "U(4)")
        self.assertEqual(result["conformal_manifold_dimension"], 1)

    def test_invalid_hyper_input_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid theory input"):
            properties.calculate_n2_theory_properties(
                {
                    "algebra": "B3",
                    "hypermultiplets": [
                        {"representation": "vector", "kind": "half"}
                    ],
                }
            )

    def test_deferred_properties_raise_not_implemented(self):
        for function in (
            properties.calculate_central_charges,
            properties.calculate_coulomb_branch_spectrum,
            properties.calculate_superconformal_indices,
        ):
            with self.subTest(function=function.__name__):
                with self.assertRaises(NotImplementedError):
                    function({})


if __name__ == "__main__":
    unittest.main()
