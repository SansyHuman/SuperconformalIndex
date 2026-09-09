"""Enumerate irreducible gauge representations with bounded Dynkin indices."""

from collections.abc import Iterable, Mapping
from fractions import Fraction
from math import lcm
from typing import Any

from anomalies.check_n2_anomalies import GaugeFactorData
from anomalies.lie_algebra import (
    DynkinLabels,
    conjugate_dynkin_labels,
    dynkin_index,
    representation_dimension, get_lie_algebra, representation_reality,
)
from common.math_utils import frobenius_solve
from common.number_utils import as_positive_fraction


def enumerate_irreps(
    gauge_factor: GaugeFactorData,
    *,
    max_index: Fraction | None = None,
    inclusive: bool = True,
    include_singlet: bool = False,
    identify_conjugates: bool = True,
) -> list[tuple[DynkinLabels, Fraction]]:
    """Return sorted pairs of Dynkin labels and exact indices within a bound.

    The default bound is twice the adjoint index (``2 * h_dual``), allowing
    half-hyper candidates. Equality is allowed unless ``inclusive=False``.
    The singlet is omitted unless ``include_singlet=True``.
    By default, retain the lexicographically larger label tuple from each
    conjugate pair, favoring lower-numbered Dynkin nodes (for example, the
    SU(n) fundamental over its antifundamental). Set
    ``identify_conjugates=False`` to return both.

    The index increases with each Dynkin label, so a rejected tuple and all
    componentwise larger tuples can be pruned from the finite search.
    """
    algebra = gauge_factor.algebra
    bound = as_positive_fraction(
        2 * algebra.dual_coxeter_number if max_index is None else max_index,
        "max_index",
    )

    zero: DynkinLabels = (0,) * algebra.rank
    pending = [zero]
    seen = {zero}
    result = []

    while pending:
        labels = pending.pop()
        index = dynkin_index(algebra, labels)
        if index > bound or (index == bound and not inclusive):
            continue

        if include_singlet or labels != zero:
            result.append((labels, index))

        for i in range(algebra.rank):
            child = labels[:i] + (labels[i] + 1,) + labels[i + 1:]
            if child not in seen:
                seen.add(child)
                pending.append(child)

    # Conjugation filters the output only; it must not prune search branches.
    if identify_conjugates:
        result = [
            (labels, index)
            for labels, index in result
            if labels >= conjugate_dynkin_labels(algebra, labels)
        ]
    return sorted(result, key=lambda x: x[0])


def enumerate_product_irreps(
    gauge_factors: Iterable[GaugeFactorData],
    *,
    max_indices: Mapping[str, Fraction] | None = None,
    inclusive: bool = True,
    include_singlet: bool = False,
    identify_conjugates: bool = True,
) -> list[tuple[dict[str, DynkinLabels], dict[str, Fraction]]]:
    """Enumerate tensor-product irreps satisfying every factor's index bound.

    For ``R = R_1 x ... x R_k``, the index for factor ``i`` is
    ``T_i(R) = T(R_i) * product_{j != i} dim(R_j)``. Each bound defaults to
    twice that factor's adjoint index (``2 * h_dual``), allowing half-hyper
    candidates. ``max_indices`` overrides bounds by factor ID. Unknown IDs
    and nonpositive or inexact bounds are rejected.

    Return pairs ``(labels_by_id, indices_by_id)``, including every factor
    in input order and sorted lexicographically by the tuples of labels in
    that order. Indices include spectator dimensions and are exact Fractions.
    Equality is allowed unless ``inclusive=False``. Singlets of individual
    factors are always considered; ``include_singlet`` controls only the
    representation trivial under the entire group.

    By default, identify a product with its simultaneous conjugate under all
    factors, keeping the lexicographically larger tuple of label tuples in
    input factor order. This favors lower-numbered Dynkin nodes in the first
    factor where the labels differ. Set ``identify_conjugates=False`` to
    return both.

    The input must contain at least one factor with distinct nonempty IDs.
    These bounds do not impose matter reality, anomaly cancellation, or
    conformality of a whole matter content.
    """
    try:
        factors = tuple(gauge_factors)
    except TypeError as exc:
        raise ValueError(
            "gauge_factors must be a nonempty iterable of GaugeFactorData objects"
        ) from exc
    if not factors or any(
        not isinstance(factor, GaugeFactorData) for factor in factors
    ):
        raise ValueError(
            "gauge_factors must be a nonempty iterable of GaugeFactorData objects"
        )

    factor_ids = tuple(factor.factor_id for factor in factors)
    if any(
        not isinstance(factor_id, str) or not factor_id.strip()
        for factor_id in factor_ids
    ):
        raise ValueError("gauge factor IDs must be nonempty strings")
    if len(set(factor_ids)) != len(factor_ids):
        raise ValueError("gauge factor IDs must be distinct")

    overrides = {} if max_indices is None else max_indices
    if not isinstance(overrides, Mapping):
        raise ValueError("max_indices must be a mapping keyed by gauge factor ID")
    unknown_ids = set(overrides) - set(factor_ids)
    if unknown_ids:
        unknown_text = ", ".join(sorted(map(str, unknown_ids)))
        raise ValueError(f"unknown gauge factor(s): {unknown_text}")
    bounds = tuple(
        as_positive_fraction(
            overrides.get(factor.factor_id, 2 * factor.algebra.dual_coxeter_number),
            f"max_indices[{factor.factor_id!r}]",
        )
        for factor in factors
    )

    # Spectator dimensions are at least one, so every allowed product uses
    # only factor irreps that already satisfy their individual index bound.
    candidates = [
        [
            (labels, index, representation_dimension(factor.algebra, labels))
            for labels, index in enumerate_irreps(
                factor,
                max_index=bound,
                inclusive=inclusive,
                include_singlet=True,
                identify_conjugates=False,
            )
        ]
        for factor, bound in zip(factors, bounds)
    ]

    result = []
    pending = [((), (), 1)]
    while pending:
        labels, indices, total_dimension = pending.pop()
        position = len(labels)
        if position == len(factors):
            if include_singlet or any(indices):
                result.append(
                    (dict(zip(factor_ids, labels)), dict(zip(factor_ids, indices)))
                )
            continue

        # Reverse insertion makes the depth-first output lexicographically sorted.
        for rep_labels, rep_index, dimension in reversed(candidates[position]):
            next_indices = tuple(value * dimension for value in indices) + (
                rep_index * total_dimension,
            )
            if any(
                value > bound or (value == bound and not inclusive)
                for value, bound in zip(next_indices, bounds)
            ):
                # Later spectator factors can only increase these indices.
                continue
            pending.append(
                (labels + (rep_labels,), next_indices, total_dimension * dimension)
            )

    # Keep all factor candidates above: independently identifying conjugates
    # would lose products such as (3, 3bar) when constructing SU(3) x SU(3).
    if identify_conjugates:
        result = [
            (labels, indices)
            for labels, indices in result
            if tuple(labels[factor_id] for factor_id in factor_ids)
            >= tuple(
                conjugate_dynkin_labels(factor.algebra, labels[factor.factor_id])
                for factor in factors
            )
        ]
    return result


def enumerate_simple_theory_candidates(
    gauge_group: str,
) -> list[dict[str, Any]]:
    """Enumerate all possible Lagrangian theory from given simple gauge group.
    gauge_group is the Cartan type of the lie algebra.
    """
    gauge_factor = GaugeFactorData("gauge", get_lie_algebra(gauge_group))
    irreps = enumerate_irreps(gauge_factor)
    realities = [
        representation_reality(
            gauge_factor.algebra,
            labels
        ) for labels, _ in irreps
    ]

    scale = lcm(*(index.denominator for _, index in irreps))
    scaled_indices = [(index * scale).numerator for _, index in irreps]
    scaled_coxeter = gauge_factor.algebra.dual_coxeter_number * scale
    for i in range(len(realities)):
        if realities[i] != "pseudoreal":
            scaled_indices[i] *= 2

    solutions = frobenius_solve(scaled_indices, 2 * scaled_coxeter)
    candidates = []
    for solution in solutions:
        theory = {
            "algebra": gauge_group,
            "hypermultiplets": []
        }
        for i in range(len(solution)):
            number = solution[i]
            if number == 0:
                continue

            theory["hypermultiplets"].append(
                {
                    "dynkin_labels": irreps[i][0],
                    "number": number,
                    "kind": "half" if realities[i] == "pseudoreal" else "full"
                }
            )

        candidates.append(theory)

    return candidates
