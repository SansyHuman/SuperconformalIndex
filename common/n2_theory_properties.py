#!/usr/bin/env python3
"""Calculate shared properties of four-dimensional N=2 Lagrangian theories.

The input JSON schema is the same one accepted by
``anomalies.check_n2_anomalies``. The implemented properties are the connected
continuous flavor symmetry at the massless point and the local complex
dimension of the conformal manifold. Central charges, the Coulomb-branch
spectrum, and superconformal indices are reserved for later integration.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any

from anomalies.check_n2_anomalies import (
    HyperData,
    ProductHyperData,
    check_input_data,
)
from anomalies.lie_algebra import DynkinLabels, conjugate_dynkin_labels


RepresentationKey = tuple[tuple[str, DynkinLabels], ...]


@dataclass
class _FlavorBlock:
    """Multiplicities of one irreducible total gauge representation."""

    key: RepresentationKey
    reality: str
    full_multiplicity: int = 0
    half_multiplicity: int = 0


def _canonical_complex_key(
    key: RepresentationKey, factor_algebras: dict[str, str]
) -> RepresentationKey:
    conjugate_key = tuple(
        (
            factor_id,
            conjugate_dynkin_labels(factor_algebras[factor_id], labels),
        )
        for factor_id, labels in key
    )
    return min(key, conjugate_key)


def _add_flavor_block(
    blocks: dict[RepresentationKey, _FlavorBlock],
    key: RepresentationKey,
    reality: str,
    kind: str,
    number: int,
    factor_algebras: dict[str, str],
) -> None:
    if number == 0:
        return
    if reality == "complex":
        key = _canonical_complex_key(key, factor_algebras)

    block = blocks.get(key)
    if block is None:
        block = _FlavorBlock(key=key, reality=reality)
        blocks[key] = block
    elif block.reality != reality:
        raise ArithmeticError(
            "equivalent gauge representations received different reality types"
        )

    if kind == "full":
        block.full_multiplicity += number
    else:
        block.half_multiplicity += number


def _simple_flavor_blocks(
    anomaly_result: dict[str, Any],
) -> tuple[dict[RepresentationKey, _FlavorBlock], dict[str, str]]:
    factor_id = "gauge"
    factor_algebras = {factor_id: anomaly_result["algebra"]}
    blocks: dict[RepresentationKey, _FlavorBlock] = {}
    hypers: list[HyperData] = anomaly_result["hypermultiplets"]

    for hyper in hypers:
        representation = hyper.representation
        key = ((factor_id, representation.labels),)
        _add_flavor_block(
            blocks,
            key,
            representation.reality,
            hyper.kind,
            hyper.number,
            factor_algebras,
        )
    return blocks, factor_algebras


def _product_flavor_blocks(
    anomaly_result: dict[str, Any],
) -> tuple[dict[RepresentationKey, _FlavorBlock], dict[str, str]]:
    factors = anomaly_result["gauge_factors"]
    factor_ids = [factor["id"] for factor in factors]
    factor_algebras = {
        factor["id"]: factor["algebra"] for factor in factors
    }
    blocks: dict[RepresentationKey, _FlavorBlock] = {}
    hypers: list[ProductHyperData] = anomaly_result["hypermultiplets"]

    for hyper in hypers:
        key = tuple(
            (factor_id, hyper.representations[factor_id].labels)
            for factor_id in factor_ids
        )
        _add_flavor_block(
            blocks,
            key,
            hyper.reality,
            hyper.kind,
            hyper.number,
            factor_algebras,
        )
    return blocks, factor_algebras


def _representation_data(
    key: RepresentationKey, factor_algebras: dict[str, str]
) -> dict[str, dict[str, Any]]:
    return {
        factor_id: {
            "algebra": factor_algebras[factor_id],
            "dynkin_labels": list(labels),
        }
        for factor_id, labels in key
    }


def _flavor_factor(
    block: _FlavorBlock, factor_algebras: dict[str, str]
) -> dict[str, Any]:
    match block.reality:
        case "complex":
            if block.half_multiplicity:
                raise ArithmeticError(
                    "a complex representation cannot contain half hypers"
                )
            multiplicity = block.full_multiplicity
            group = f"U({multiplicity})"
            lie_algebra = f"u({multiplicity})"
            rank = multiplicity
            dimension = multiplicity**2
            half_hyper_units = 2 * multiplicity
        case "real":
            if block.half_multiplicity:
                raise ArithmeticError(
                    "a real representation cannot contain half hypers"
                )
            multiplicity = block.full_multiplicity
            group = f"Sp({multiplicity})"
            lie_algebra = f"sp({multiplicity})"
            rank = multiplicity
            dimension = multiplicity * (2 * multiplicity + 1)
            half_hyper_units = 2 * multiplicity
        case "pseudoreal":
            half_hyper_units = (
                block.half_multiplicity + 2 * block.full_multiplicity
            )
            group = f"SO({half_hyper_units})"
            lie_algebra = f"so({half_hyper_units})"
            rank = half_hyper_units // 2
            dimension = half_hyper_units * (half_hyper_units - 1) // 2
        case _:
            raise ArithmeticError(
                f"unexpected representation reality {block.reality!r}"
            )

    return {
        "group": group,
        "lie_algebra": lie_algebra,
        "rank": rank,
        "dimension": dimension,
        "representation_reality": block.reality,
        "full_hypermultiplets": block.full_multiplicity,
        "half_hypermultiplets": block.half_multiplicity,
        "half_hyper_units": half_hyper_units,
        "gauge_representation": _representation_data(
            block.key, factor_algebras
        ),
    }


def _calculate_flavor_symmetry(
    anomaly_result: dict[str, Any],
) -> dict[str, Any]:
    if "gauge_factors" in anomaly_result:
        blocks, factor_algebras = _product_flavor_blocks(anomaly_result)
    else:
        blocks, factor_algebras = _simple_flavor_blocks(anomaly_result)

    factors = [
        _flavor_factor(block, factor_algebras) for block in blocks.values()
    ]
    nontrivial_groups = [
        factor["group"] for factor in factors if factor["dimension"] > 0
    ]
    return {
        "connected_group": (
            " x ".join(nontrivial_groups) if nontrivial_groups else "trivial"
        ),
        "rank": sum(factor["rank"] for factor in factors),
        "dimension": sum(factor["dimension"] for factor in factors),
        "factors": factors,
    }


def _exactly_marginal_gauge_couplings(
    anomaly_result: dict[str, Any],
) -> list[str]:
    if not anomaly_result["lagrangian_scft_candidate"]:
        return []
    if "gauge_factors" in anomaly_result:
        return [factor["id"] for factor in anomaly_result["gauge_factors"]]
    return ["gauge"]


def calculate_n2_theory_properties(data: dict[str, Any]) -> dict[str, Any]:
    """Calculate implemented properties from an anomaly-checker JSON object."""
    anomaly_result = check_input_data(data)
    if anomaly_result["errors"]:
        messages = "; ".join(anomaly_result["errors"])
        raise ValueError(f"invalid theory input: {messages}")

    marginal_couplings = _exactly_marginal_gauge_couplings(anomaly_result)
    conformal_dimension = (
        len(marginal_couplings)
        if anomaly_result["lagrangian_scft_candidate"]
        else None
    )
    return {
        "group": anomaly_result["group"],
        "lagrangian_scft_candidate": anomaly_result[
            "lagrangian_scft_candidate"
        ],
        "flavor_symmetry": _calculate_flavor_symmetry(anomaly_result),
        "conformal_manifold_dimension": conformal_dimension,
        "exactly_marginal_gauge_couplings": marginal_couplings,
        "central_charges": None,
        "coulomb_branch_spectrum": None,
        "superconformal_indices": None,
    }


def calculate_n2_theory_properties_from_file(
    path: str | Path,
) -> dict[str, Any]:
    """Load an anomaly-checker JSON file and calculate implemented properties."""
    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return calculate_n2_theory_properties(data)


def calculate_central_charges(data: dict[str, Any]) -> Any:
    raise NotImplementedError("central charges are not implemented in this module")


def calculate_coulomb_branch_spectrum(data: dict[str, Any]) -> Any:
    raise NotImplementedError(
        "the Coulomb-branch spectrum is not implemented in this module"
    )


def calculate_superconformal_indices(data: dict[str, Any]) -> Any:
    raise NotImplementedError(
        "superconformal indices are not implemented in this module"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="path to the theory JSON file")
    args = parser.parse_args(argv)
    try:
        result = calculate_n2_theory_properties_from_file(args.input)
    except (OSError, json.JSONDecodeError, ValueError, ArithmeticError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
