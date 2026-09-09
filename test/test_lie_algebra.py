from itertools import combinations_with_replacement
from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from anomalies.lie_algebra import get_lie_algebra, representation_reality


REALITY_CARTAN_TYPES = (
    "A1", "A2", "A3", "A4", "A5", "A6",
    "B2", "B3", "B4", "B5",
    "C2", "C3", "C4", "C5",
    "D4", "D5", "D6", "D7",
    "E6", "E7", "E8", "F4", "G2",
)


def small_irrep_labels(algebra):
    """Keep Sage's tensor-square oracle bounded while covering every family."""
    candidates = {algebra.adjoint_labels}
    for total in range(3):
        for nodes in combinations_with_replacement(range(algebra.rank), total):
            labels = [0] * algebra.rank
            for node in nodes:
                labels[node] += 1
            labels = tuple(labels)
            if algebra.character_ring(labels).degree() <= 64:
                candidates.add(labels)
    if algebra.cartan_type == "A1":
        candidates.update((label,) for label in range(9))
    return sorted(candidates)


class RepresentationRealityTests(unittest.TestCase):
    def test_matches_sage_indicator_across_all_families(self):
        # Includes singlets and adjoints, complex conjugate pairs, the
        # pseudoreal SU(6) 20, and real/complex/pseudoreal Spin spinors.
        expected_types = {-1: "pseudoreal", 0: "complex", 1: "real"}
        observed_types = set()
        for cartan_type in REALITY_CARTAN_TYPES:
            algebra = get_lie_algebra(cartan_type)
            for labels in small_irrep_labels(algebra):
                with self.subTest(cartan_type=cartan_type, labels=labels):
                    character = algebra.character_ring(labels)
                    indicator = int(character.frobenius_schur_indicator())
                    expected = expected_types[indicator]
                    observed_types.add(expected)
                    self.assertEqual(
                        representation_reality(algebra, labels), expected
                    )
        self.assertEqual(observed_types, set(expected_types.values()))

    def test_accepts_algebra_strings_and_one_shot_label_iterables(self):
        self.assertEqual(representation_reality("A2", iter([1, 0])), "complex")
        self.assertEqual(representation_reality("C2", iter([1, 1])), "pseudoreal")
        self.assertEqual(representation_reality("C2", [0, 1]), "real")

    def test_invalid_labels_still_raise_value_error(self):
        for labels in (None, [1], [1, 0, 0], [-1, 0], [0.5, 0], [True, 0]):
            with self.subTest(labels=labels):
                with self.assertRaises(ValueError):
                    representation_reality("A2", labels)


if __name__ == "__main__":
    unittest.main()
