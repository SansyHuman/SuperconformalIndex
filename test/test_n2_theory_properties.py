from contextlib import redirect_stdout
from fractions import Fraction
from io import StringIO
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from common import n2_theory_properties as properties


class TheoryPropertyTests(unittest.TestCase):
    def setUp(self):
        index_patcher = patch.object(
            properties,
            "calculate_index_internal",
            return_value="mock_index",
        )
        self.calculate_index_internal = index_patcher.start()
        self.addCleanup(index_patcher.stop)
        coulomb_index_patcher = patch.object(
            properties,
            "calculate_lagrangian_coulomb_branch_index",
            return_value="mock_coulomb_index",
        )
        self.calculate_lagrangian_coulomb_branch_index = (
            coulomb_index_patcher.start()
        )
        self.addCleanup(coulomb_index_patcher.stop)

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
        self.assertEqual(
            result["flavor_symmetry"]["factors"][0]["gauge_representation"]
            ["gauge"]["dynkin_labels"],
            [1, 0],
        )
        self.assertEqual(result["conformal_manifold_dimension"], 1)
        self.assertEqual(
            result["central_charges"],
            {"a": Fraction(29, 12), "c": Fraction(17, 6)},
        )

    def test_complex_flavor_blocks_prefer_lower_dynkin_nodes(self):
        cases = (
            ("A4", (1, 0, 0, 0), (0, 0, 0, 1)),
            ("D5", (0, 0, 0, 1, 0), (0, 0, 0, 0, 1)),
            ("E6", (1, 0, 0, 0, 0, 0), (0, 0, 0, 0, 0, 1)),
        )
        for algebra, preferred, conjugate in cases:
            for labels in (preferred, conjugate):
                with self.subTest(algebra=algebra, labels=labels):
                    result = properties.calculate_n2_theory_properties({
                        "algebra": algebra,
                        "hypermultiplets": [{"dynkin_labels": labels}],
                    })
                    representation = result["flavor_symmetry"]["factors"][0][
                        "gauge_representation"
                    ]["gauge"]
                    self.assertEqual(representation["dynkin_labels"], list(preferred))

    def test_product_flavor_blocks_use_only_simultaneous_conjugation(self):
        fundamental, antifundamental = (1, 0), (0, 1)
        canonical_representations = set()
        for left, right, expected in (
            (fundamental, fundamental, (fundamental, fundamental)),
            (antifundamental, antifundamental, (fundamental, fundamental)),
            (fundamental, antifundamental, (fundamental, antifundamental)),
            (antifundamental, fundamental, (fundamental, antifundamental)),
        ):
            with self.subTest(left=left, right=right):
                result = properties.calculate_n2_theory_properties({
                    "gauge_groups": [
                        {"id": "left", "algebra": "A2"},
                        {"id": "right", "algebra": "A2"},
                    ],
                    "hypermultiplets": [{
                        "representations": {"left": list(left), "right": list(right)},
                        "number": 2,
                    }],
                })
                block = result["flavor_symmetry"]["factors"][0]
                self.assertEqual(block["group"], "U(2)")
                representation = tuple(
                    tuple(block["gauge_representation"][factor]["dynkin_labels"])
                    for factor in ("left", "right")
                )
                self.assertEqual(representation, expected)
                canonical_representations.add(representation)
        self.assertEqual(len(canonical_representations), 2)

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
        self.assertEqual(
            result["central_charges"],
            {"a": Fraction(19, 12), "c": Fraction(5, 3)},
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
        self.assertIsNone(result["central_charges"])

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
        self.assertEqual(
            result["central_charges"],
            {"a": Fraction(83, 4), "c": Fraction(22)},
        )

    def test_main_serializes_central_charges_exactly(self):
        path = PROJECT_ROOT / "anomalies" / "example_e6.json"
        output = StringIO()

        with redirect_stdout(output):
            exit_code = properties.main([str(path)])

        result = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(
            result["central_charges"],
            {
                "a": {"numerator": 83, "denominator": 4},
                "c": {"numerator": 22, "denominator": 1},
            },
        )
        self.assertEqual(
            result["coulomb_branch_spectrum"],
            [
                {"numerator": 2, "denominator": 1},
                {"numerator": 5, "denominator": 1},
                {"numerator": 6, "denominator": 1},
                {"numerator": 8, "denominator": 1},
                {"numerator": 9, "denominator": 1},
                {"numerator": 12, "denominator": 1},
            ],
        )

    def test_public_central_charge_api_counts_half_hypers(self):
        central_charges = properties.calculate_central_charges(
            {
                "algebra": "A1",
                "hypermultiplets": [
                    {
                        "representation": "fundamental",
                        "kind": "half",
                        "number": 8,
                    }
                ],
            }
        )

        self.assertEqual(
            central_charges,
            {"a": Fraction(23, 24), "c": Fraction(7, 6)},
        )

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

    def test_public_coulomb_branch_index_uses_lagrangian_calculation(self):
        result = properties.calculate_coulomb_branch_index(
            {
                "algebra": "A1",
                "hypermultiplets": [
                    {"representation": "fundamental", "number": 4}
                ],
            }
        )

        self.assertEqual(result, "mock_coulomb_index")
        self.calculate_lagrangian_coulomb_branch_index.assert_called_once()

    def test_public_coulomb_branch_spectrum_uses_gauge_factors(self):
        result = properties.calculate_coulomb_branch_spectrum(
            {
                "algebra": "A2",
                "hypermultiplets": [
                    {"representation": "fundamental", "number": 6}
                ],
            }
        )

        self.assertEqual(result, (Fraction(2), Fraction(3)))

    def test_indices_and_coulomb_spectrum_use_singular_keys(self):
        data = {
            "algebra": "A1",
            "hypermultiplets": [
                {"representation": "fundamental", "number": 4}
            ],
        }

        result = properties.calculate_n2_theory_properties(data)

        self.assertEqual(result["coulomb_branch_index"], "mock_coulomb_index")
        self.assertEqual(
            result["coulomb_branch_spectrum"],
            (Fraction(2),),
        )
        self.assertEqual(result["superconformal_index"], "mock_index")
        self.assertNotIn("superconformal_indices", result)
        self.calculate_index_internal.assert_called_once()

    def test_public_superconformal_index_uses_internal_calculation(self):
        result = properties.calculate_superconformal_index(
            {
                "algebra": "A1",
                "hypermultiplets": [
                    {"representation": "fundamental", "number": 4}
                ],
            }
        )

        self.assertEqual(result, "mock_index")
        self.calculate_index_internal.assert_called_once()


if __name__ == "__main__":
    unittest.main()
