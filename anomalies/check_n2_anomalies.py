#!/usr/bin/env python3
"""Check anomalies and one-loop beta functions of 4d N=2 gauge theories.

Scope
-----
* Each gauge factor is the simply connected compact group for a finite simple
  Cartan type A, B, C, D, E, F, or G.
* A full hypermultiplet in R contains N=1 chirals in R and conjugate(R).
* A half hypermultiplet is accepted only when R is pseudoreal.
* Conventional Witten anomalies of SU(2) and Sp(n) are checked on spin
  four-manifolds.
* Pure 't Hooft anomalies of ungauged flavor symmetries are intentionally not
  required to vanish.
* SageMath supplies Cartan/root data, Weyl-character dimensions and duals,
  and Frobenius-Schur reality indicators. Casimirs and indices remain exact.

Input is a JSON file of the form

    {
      "algebra": "A4",
      "hypermultiplets": [
        {"representation": "symmetric", "number": 1},
        {"representation": "antisymmetric", "number": 1}
      ]
    }

The default kind is "full". An arbitrary irreducible representation can be
supplied through its Bourbaki Dynkin labels, for example

    {"dynkin_labels": [1], "number": 2, "kind": "half"}

for two SU(2) fundamental half hypermultiplets.

A general single-factor input uses a Bourbaki Cartan type::

    {
      "algebra": "E6",
      "hypermultiplets": [
        {"dynkin_labels": [1, 0, 0, 0, 0, 0], "number": 4}
      ]
    }

A product-group input uses named gauge factors and a representation for each
nontrivial factor.  Omitted factors are treated as singlets::

    {
      "gauge_groups": [
        {"id": "left", "algebra": "C2"},
        {"id": "right", "algebra": "D4"}
      ],
      "hypermultiplets": [
        {
          "representations": {
            "left": "fundamental",
            "right": "fundamental"
          },
          "number": 2,
          "kind": "full"
        }
      ]
    }
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable

if __package__:
    from .lie_algebra import (
        SimpleLieAlgebra,
        dynkin_index as lie_dynkin_index,
        get_lie_algebra,
        named_representation_labels,
        representation_dimension as lie_representation_dimension,
        representation_reality as lie_representation_reality,
        validate_dynkin_labels,
    )
else:  # Support direct execution: sage -python anomalies/check_n2_anomalies.py
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from lie_algebra import (
        SimpleLieAlgebra,
        dynkin_index as lie_dynkin_index,
        get_lie_algebra,
        named_representation_labels,
        representation_dimension as lie_representation_dimension,
        representation_reality as lie_representation_reality,
        validate_dynkin_labels,
    )

from common.number_utils import as_nonnegative_int


@dataclass(frozen=True)
class RepresentationData:
    """Data of single representation."""
    # Name of the representation
    name: str
    # Dynkin labels of the representation
    labels: tuple[int, ...]
    # Dimension of the representation
    dimension: int
    # Dynkin index of the representation
    dynkin_index: Fraction
    # Reality type; one of real, pseudoreal, and complex
    reality: str


@dataclass(frozen=True)
class HyperData:
    """Data of simple-factor hypermultiplet."""
    # Representation of the hypermultiplet
    representation: RepresentationData
    # Multiplicity of the multiplet
    number: int
    # Full or half hypermultiplet
    kind: str
    # Contribution to the beta function
    beta_contribution: Fraction


@dataclass(frozen=True)
class GaugeFactorData:
    """Simple object for each gauge groups of product group."""
    # Identifier of the gauge group
    factor_id: str
    # Gauge group algebra
    algebra: SimpleLieAlgebra

    @property
    def group(self) -> str:
        return self.algebra.group


@dataclass(frozen=True)
class ProductHyperData:
    """Data of hypermultiplet in product of representations."""
    # Name of the hypermultiplet
    name: str
    # Product of representations with each gauge factor
    representations: dict[str, RepresentationData]
    # Dimension of representation
    dimension: int
    # Reality type of the representation
    reality: str
    # Multiplicity of the multiplet
    number: int
    # Full or half hypermultiplet
    kind: str
    # Contribution to beta functions of each gauge factor
    beta_contributions: dict[str, Fraction]


def _fraction_text(value: Fraction) -> str:
    """Convert Fraction number to string representation."""
    return str(value.numerator) if value.denominator == 1 else str(value)


def parse_lie_representation(
    algebra: SimpleLieAlgebra | str, item: dict[str, Any]
) -> RepresentationData:
    """Converts representation name or dynkin labels to RepresentationData."""
    algebra = (
        algebra
        if isinstance(algebra, SimpleLieAlgebra)
        else get_lie_algebra(algebra)
    )
    if "dynkin_labels" in item:
        labels = validate_dynkin_labels(algebra, item["dynkin_labels"])
        name = item.get("name", f"Dynkin{list(labels)}")
    elif "representation" in item:
        raw = item["representation"]
        if isinstance(raw, str):
            labels = named_representation_labels(algebra, raw)
            name = raw
        elif isinstance(raw, list):
            labels = validate_dynkin_labels(algebra, raw)
            name = item.get("name", f"Dynkin{list(labels)}")
        else:
            raise ValueError("representation must be a name or a list of Dynkin labels")
    else:
        raise ValueError("each hypermultiplet needs representation or dynkin_labels")

    return RepresentationData(
        name=str(name),
        labels=labels,
        dimension=lie_representation_dimension(algebra, labels),
        dynkin_index=lie_dynkin_index(algebra, labels),
        reality=lie_representation_reality(algebra, labels),
    )


def check_simple_theory(
    algebra: SimpleLieAlgebra | str, hypermultiplets: list[dict[str, Any]]
) -> dict[str, Any]:
    """Check one simply connected simple gauge factor."""
    algebra = (
        algebra
        if isinstance(algebra, SimpleLieAlgebra)
        else get_lie_algebra(algebra)
    )
    if not isinstance(hypermultiplets, list):
        raise ValueError("hypermultiplets must be a list")

    hypers: list[HyperData] = []
    errors: list[str] = []
    beta_matter = Fraction(0)
    witten_parity = 0 if algebra.has_witten_anomaly else None

    for position, item in enumerate(hypermultiplets, start=1):
        if not isinstance(item, dict):
            errors.append(f"hypermultiplet {position}: entry must be an object")
            continue
        try:
            rep = parse_lie_representation(algebra, item)
            number = as_nonnegative_int(
                item.get("number", item.get("multiplicity", 1)), "number"
            )
            kind = str(item.get("kind", "full")).strip().lower()
            if kind not in {"full", "half"}:
                raise ValueError("kind must be 'full' or 'half'")
            if kind == "half" and rep.reality != "pseudoreal":
                raise ValueError(
                    f"a half hyper requires a pseudoreal representation, but "
                    f"{rep.name} is {rep.reality}"
                )

            contribution = number * rep.dynkin_index * (2 if kind == "full" else 1)
            next_parity = witten_parity
            if witten_parity is not None and kind == "half":
                two_t = 2 * rep.dynkin_index
                if two_t.denominator != 1:
                    raise ArithmeticError(
                        f"2 T(R) should be integral for {algebra.group}"
                    )
                next_parity = witten_parity ^ ((number * two_t.numerator) & 1)

            # Commit only after every validation for this hyper succeeds.
            beta_matter += contribution
            hypers.append(HyperData(rep, number, kind, contribution))
            witten_parity = next_parity
        except (ValueError, ArithmeticError) as exc:
            errors.append(f"hypermultiplet {position}: {exc}")

    # Valid full N=2 hypers are vectorlike.  Valid half hypers are pseudoreal,
    # whose perturbative cubic anomaly vanishes.  The adjoint gauginos are real.
    perturbative_gauge_anomaly_free = not errors
    global_gauge_anomaly_free = not errors and (
        witten_parity is None or witten_parity == 0
    )
    anomaly_free = (
        perturbative_gauge_anomaly_free
        and global_gauge_anomaly_free
    )

    vector_contribution = Fraction(2 * algebra.dual_coxeter_number)
    b0 = vector_contribution - beta_matter

    return {
        "group": algebra.group,
        "algebra": algebra.cartan_type,
        "rank": algebra.rank,
        "hypermultiplets": hypers,
        "errors": errors,
        "perturbative_gauge_anomaly_free": perturbative_gauge_anomaly_free,
        "global_gauge_anomaly_free": global_gauge_anomaly_free,
        "witten_anomaly_parity": witten_parity,
        "anomaly_free": anomaly_free,
        "vector_beta_contribution": vector_contribution,
        "matter_beta_contribution": beta_matter,
        "b0": b0,
        "one_loop_beta_vanishes": not errors and b0 == 0,
        "lagrangian_scft_candidate": anomaly_free and b0 == 0,
    }


def parse_gauge_factors(gauge_groups: list[dict[str, Any]]) -> list[GaugeFactorData]:
    """Parse named simply connected simple factors of finite Cartan type."""
    if not isinstance(gauge_groups, list) or not gauge_groups:
        raise ValueError("gauge_groups must be a nonempty list")

    factors: list[GaugeFactorData] = []
    seen_ids: set[str] = set()
    for position, item in enumerate(gauge_groups, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"gauge group {position}: entry must be an object")
        if "algebra" not in item:
            raise ValueError(f"gauge group {position}: missing algebra")
        algebra = get_lie_algebra(item["algebra"])
        factor_id = str(item.get("id", f"g{position}")).strip()
        if not factor_id:
            raise ValueError(f"gauge group {position}: id must not be empty")
        if factor_id in seen_ids:
            raise ValueError(f"gauge group {position}: duplicate id {factor_id!r}")
        seen_ids.add(factor_id)
        factors.append(GaugeFactorData(factor_id, algebra))
    return factors


def _parse_product_representation(
    factor: GaugeFactorData, specification: Any
) -> RepresentationData:
    """Apply representation parser to every factor."""
    if isinstance(specification, str):
        item = {"representation": specification}
    elif isinstance(specification, list):
        item = {"representation": specification}
    elif isinstance(specification, dict):
        item = specification
    else:
        raise ValueError(
            f"representation for {factor.factor_id} must be a name, "
            "Dynkin-label list, or object"
        )
    return parse_lie_representation(factor.algebra, item)


def _product_reality(representations: Iterable[RepresentationData]) -> str:
    """Reality type of an external tensor product of irreducible factors."""
    realities = [representation.reality for representation in representations]
    if "complex" in realities:
        return "complex"
    pseudoreal_count = sum(reality == "pseudoreal" for reality in realities)
    return "pseudoreal" if pseudoreal_count % 2 else "real"


def check_product_theory(
    gauge_groups: list[dict[str, Any]], hypermultiplets: list[dict[str, Any]]
) -> dict[str, Any]:
    """Check a product of simply connected simple compact gauge factors.

    For a hyper in the external tensor product ``R_1 x ... x R_k``, its
    contribution to factor ``a`` is multiplied by the dimensions of all
    spectator representations: ``T_a(R_a) * product_{b != a} dim(R_b)``.
    """
    factors = parse_gauge_factors(gauge_groups)
    if not isinstance(hypermultiplets, list):
        raise ValueError("hypermultiplets must be a list")

    factor_by_id = {factor.factor_id: factor for factor in factors}
    matter = {factor.factor_id: Fraction(0) for factor in factors}
    witten_parity = {
        factor.factor_id: 0
        for factor in factors
        if factor.algebra.has_witten_anomaly
    }
    hypers: list[ProductHyperData] = []
    errors: list[str] = []

    for position, item in enumerate(hypermultiplets, start=1):
        if not isinstance(item, dict):
            errors.append(f"hypermultiplet {position}: entry must be an object")
            continue
        try:
            raw_representations = item.get("representations")
            if not isinstance(raw_representations, dict):
                raise ValueError("representations must be an object keyed by gauge id")
            unknown_ids = set(raw_representations) - set(factor_by_id)
            if unknown_ids:
                unknown_text = ", ".join(sorted(map(str, unknown_ids)))
                raise ValueError(f"unknown gauge factor(s): {unknown_text}")

            representations: dict[str, RepresentationData] = {}
            for factor in factors:
                specification = raw_representations.get(factor.factor_id, "singlet")
                representations[factor.factor_id] = _parse_product_representation(
                    factor, specification
                )

            number = as_nonnegative_int(
                item.get("number", item.get("multiplicity", 1)), "number"
            )
            kind = str(item.get("kind", "full")).strip().lower()
            if kind not in {"full", "half"}:
                raise ValueError("kind must be 'full' or 'half'")

            total_reality = _product_reality(representations.values())
            if kind == "half" and total_reality != "pseudoreal":
                raise ValueError(
                    "a half hyper requires an overall pseudoreal "
                    f"representation, but this tensor product is {total_reality}"
                )

            total_dimension = 1
            for representation in representations.values():
                total_dimension *= representation.dimension

            coefficient = 2 if kind == "full" else 1
            contributions: dict[str, Fraction] = {}
            next_parities = dict(witten_parity)
            for factor in factors:
                representation = representations[factor.factor_id]
                spectator_dimension = total_dimension // representation.dimension
                contribution = (
                    number
                    * coefficient
                    * representation.dynkin_index
                    * spectator_dimension
                )
                contributions[factor.factor_id] = contribution

                if factor.factor_id in witten_parity and kind == "half":
                    two_t_with_spectators = (
                        2 * representation.dynkin_index * spectator_dimension
                    )
                    if two_t_with_spectators.denominator != 1:
                        raise ArithmeticError(
                            "2 T(R) times spectator dimension should be integral "
                            f"for {factor.factor_id}"
                        )
                    next_parities[factor.factor_id] ^= (
                        number * two_t_with_spectators.numerator
                    ) & 1

            # Commit the hyper only after every factor has passed validation.
            for factor_id, contribution in contributions.items():
                matter[factor_id] += contribution
            witten_parity = next_parities

            default_name = " x ".join(
                f"{factor.factor_id}:{representations[factor.factor_id].name}"
                for factor in factors
            )
            hypers.append(
                ProductHyperData(
                    name=str(item.get("name", default_name)),
                    representations=representations,
                    dimension=total_dimension,
                    reality=total_reality,
                    number=number,
                    kind=kind,
                    beta_contributions=contributions,
                )
            )
        except (ValueError, ArithmeticError) as exc:
            errors.append(f"hypermultiplet {position}: {exc}")

    factor_results: list[dict[str, Any]] = []
    for factor in factors:
        algebra = factor.algebra
        vector = Fraction(2 * algebra.dual_coxeter_number)
        b0 = vector - matter[factor.factor_id]
        parity = witten_parity.get(factor.factor_id)
        global_free = not errors and (parity is None or parity == 0)
        factor_results.append(
            {
                "id": factor.factor_id,
                "group": factor.group,
                "algebra": algebra.cartan_type,
                "rank": algebra.rank,
                "vector_beta_contribution": vector,
                "matter_beta_contribution": matter[factor.factor_id],
                "b0": b0,
                "one_loop_beta_vanishes": not errors and b0 == 0,
                "witten_anomaly_parity": parity,
                "global_gauge_anomaly_free": global_free,
            }
        )

    perturbative_free = not errors
    global_free = not errors and all(
        factor["global_gauge_anomaly_free"] for factor in factor_results
    )
    anomaly_free = perturbative_free and global_free
    all_betas_vanish = not errors and all(
        factor["b0"] == 0 for factor in factor_results
    )

    return {
        "group": " x ".join(factor.group for factor in factors),
        "gauge_factors": factor_results,
        "hypermultiplets": hypers,
        "errors": errors,
        "perturbative_gauge_anomaly_free": perturbative_free,
        "global_gauge_anomaly_free": global_free,
        "anomaly_free": anomaly_free,
        "one_loop_beta_vanishes": all_betas_vanish,
        "lagrangian_scft_candidate": anomaly_free and all_betas_vanish,
    }


def format_report(result: dict[str, Any]) -> str:
    if "gauge_factors" in result:
        return format_product_report(result)

    lines = [f"Gauge group: {result['group']}", "", "Hypermultiplets:"]
    hypers: list[HyperData] = result["hypermultiplets"]
    if not hypers:
        lines.append("  (none successfully parsed)")
    for hyper in hypers:
        rep = hyper.representation
        lines.append(
            f"  - {hyper.number} x {hyper.kind} {rep.name}: "
            f"Dynkin labels={list(rep.labels)}, dim={rep.dimension}, "
            f"T(R)={_fraction_text(rep.dynkin_index)}, type={rep.reality}, "
            f"beta matter contribution={_fraction_text(hyper.beta_contribution)}"
        )

    if result["errors"]:
        lines.extend(["", "Input/representation errors:"])
        lines.extend(f"  - {message}" for message in result["errors"])

    local_text = "PASS" if result["perturbative_gauge_anomaly_free"] else "FAIL"
    global_text = "PASS" if result["global_gauge_anomaly_free"] else "FAIL"
    overall_text = "YES" if result["anomaly_free"] else "NO"
    beta_text = "YES" if result["one_loop_beta_vanishes"] else "NO"
    scft_text = "YES" if result["lagrangian_scft_candidate"] else "NO"

    lines.extend(
        [
            "",
            "Checks:",
            f"  Perturbative gauge anomaly: {local_text}",
            f"  Global gauge anomaly:       {global_text}",
        ]
    )
    if result["witten_anomaly_parity"] is not None:
        lines.append(
            f"  {result['group']} Witten anomaly parity: "
            f"{result['witten_anomaly_parity']} (0 is anomaly-free)"
        )
    lines.extend(
        [
            f"  Overall anomaly-free:       {overall_text}",
            "",
            "One-loop N=2 beta function (long roots have length squared 2):",
            f"  vector contribution = {_fraction_text(result['vector_beta_contribution'])}",
            f"  matter contribution = {_fraction_text(result['matter_beta_contribution'])}",
            f"  b0 = {_fraction_text(result['b0'])}",
            f"  b0 vanishes: {beta_text}",
            f"  Anomaly-free Lagrangian SCFT candidate: {scft_text}",
            "",
            "Note: this assumes the simply connected group of the stated Cartan",
            "type, not a quotient. Pure flavor 't Hooft anomalies are not tested.",
        ]
    )
    return "\n".join(lines)


def format_product_report(result: dict[str, Any]) -> str:
    lines = [f"Gauge group: {result['group']}", "", "Hypermultiplets:"]
    hypers: list[ProductHyperData] = result["hypermultiplets"]
    if not hypers:
        lines.append("  (none successfully parsed)")
    for hyper in hypers:
        lines.append(
            f"  - {hyper.number} x {hyper.kind} {hyper.name}: "
            f"dim={hyper.dimension}, type={hyper.reality}"
        )
        for factor_id, representation in hyper.representations.items():
            contribution = hyper.beta_contributions[factor_id]
            lines.append(
                f"      {factor_id}: {representation.name}, "
                f"Dynkin labels={list(representation.labels)}, "
                f"dim={representation.dimension}, "
                f"T(R)={_fraction_text(representation.dynkin_index)}, "
                f"beta contribution={_fraction_text(contribution)}"
            )

    if result["errors"]:
        lines.extend(["", "Input/representation errors:"])
        lines.extend(f"  - {message}" for message in result["errors"])

    local_text = "PASS" if result["perturbative_gauge_anomaly_free"] else "FAIL"
    global_text = "PASS" if result["global_gauge_anomaly_free"] else "FAIL"
    overall_text = "YES" if result["anomaly_free"] else "NO"
    beta_text = "YES" if result["one_loop_beta_vanishes"] else "NO"
    scft_text = "YES" if result["lagrangian_scft_candidate"] else "NO"
    lines.extend(
        [
            "",
            "Checks:",
            f"  Perturbative gauge anomaly: {local_text}",
            f"  Global gauge anomaly:       {global_text}",
            f"  Overall anomaly-free:       {overall_text}",
            "",
            "One-loop N=2 beta functions (long roots have length squared 2):",
        ]
    )
    for factor in result["gauge_factors"]:
        lines.append(
            f"  {factor['id']} ({factor['group']}): vector="
            f"{_fraction_text(factor['vector_beta_contribution'])}, matter="
            f"{_fraction_text(factor['matter_beta_contribution'])}, "
            f"b0={_fraction_text(factor['b0'])}"
        )
        if factor["witten_anomaly_parity"] is not None:
            lines.append(
                f"    {factor['group']} Witten anomaly parity: "
                f"{factor['witten_anomaly_parity']} (0 is anomaly-free)"
            )
    lines.extend(
        [
            f"  Every b0 vanishes: {beta_text}",
            f"  Anomaly-free Lagrangian SCFT candidate: {scft_text}",
            "",
            "Note: this assumes simply connected factors of the stated Cartan",
            "types, not quotients. Pure flavor 't Hooft anomalies are not tested.",
        ]
    )
    return "\n".join(lines)


def _validate_input_shape(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("the JSON root must be an object")
    modes = [key for key in ("algebra", "gauge_groups") if key in data]
    if not modes:
        raise ValueError("the JSON input needs algebra or gauge_groups")
    if len(modes) != 1:
        raise ValueError("use exactly one of algebra or gauge_groups")
    return data


def _load_input(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return _validate_input_shape(data)


def check_input_data(data: dict[str, Any]) -> dict[str, Any]:
    """Check a simple-factor or product-theory JSON object."""
    data = _validate_input_shape(data)
    hypermultiplets = data.get("hypermultiplets", [])
    if "algebra" in data:
        return check_simple_theory(data["algebra"], hypermultiplets)
    return check_product_theory(data["gauge_groups"], hypermultiplets)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="path to the theory JSON file")
    args = parser.parse_args(argv)
    try:
        data = _load_input(args.input)
        result = check_input_data(data)
    except (OSError, json.JSONDecodeError, ValueError, ArithmeticError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(format_report(result))
    return 0 if result["anomaly_free"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
