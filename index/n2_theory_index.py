#!/usr/bin/env python3
"""Calculate the 4d N=2 index for simple and product groups with FORM and LiE.

The input conventions agree with ``anomalies.check_n2_anomalies``. FORM expands
the exact, truncated representation-valued plethystic exponential. LiE
decomposes products of Adams-operated characters, and the file cache in
``index.char_decomposition_cache`` stores those decompositions by canonical
Cartan type and Dynkin labels.

For a product gauge group, FORM keeps a separate formal character for each
simple factor and LiE performs the singlet projection factor by factor.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from fractions import Fraction
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sage.all import LaurentPolynomialRing, QQ, sage_eval

from anomalies.check_n2_anomalies import (
    GaugeFactorData,
    HyperData,
    ProductHyperData,
    check_input_data,
)
from anomalies.lie_algebra import (
    DynkinLabels,
    _as_nonnegative_int,
    conjugate_dynkin_labels,
    get_lie_algebra,
)
from index.char_decomposition_cache import (
    AdamsPowers,
    CharacterDecompositionCache,
    Decomposition,
)


# A pair (gauge factor position, highest weight of representation)
CharacterSpec = tuple[int, DynkinLabels]
# Character of external tensor product representations
CharacterMonomial = tuple[CharacterSpec, ...]
# Character monomial after every character has been assigned a FORM character number
IndexedMonomial = tuple[int, ...]

INDEX_POLYNOMIAL_RING = LaurentPolynomialRing(
    QQ, 3, names=("t", "y", "u")
)
_INDEX_POLYNOMIAL_TEXT_PATTERN = re.compile(r"[0-9tyu+\-*/^()\s]+")


@dataclass(frozen=True)
class FormTerm:
    """One FORM monomial before gauge-singlet projection."""

    # Coefficient of the term
    coefficient: Fraction
    # Power of t
    t_power: int
    # Power of y fugacity
    y_power: int
    # Power of u fugacity
    u_power: int
    # products of characters with (character index, Adams powers of the character)
    characters: tuple[tuple[int, AdamsPowers], ...]


_RATIONAL_RE = re.compile(r"d\((-?\d+),(-?\d+)\)\Z")
_CHARACTER_RE = re.compile(r"C(\d+)\((\d+)\)(?:\^(\d+))?\Z")
_FUGACITY_RE = re.compile(r"([tyu])(?:\^(-?\d+))?\Z")
_INTEGER_RE = re.compile(r"\d+\Z")


def _parse_input(
    data: dict[str, Any],
) -> tuple[tuple[GaugeFactorData, ...], list[HyperData | ProductHyperData]]:
    """Validate either JSON convention and return ordered gauge factors."""
    result = check_input_data(data)
    if result["errors"]:
        raise ValueError("; ".join(result["errors"]))

    if "gauge_factors" in result:
        factors = tuple(
            GaugeFactorData(
                factor["id"], get_lie_algebra(factor["algebra"])
            )
            for factor in result["gauge_factors"]
        )
    else:
        factors = (
            GaugeFactorData("gauge", get_lie_algebra(result["algebra"])),
        )
    return factors, result["hypermultiplets"]


def _matter_character_multiplicities(
    factors: tuple[GaugeFactorData, ...],
    hypermultiplets: list[HyperData | ProductHyperData],
) -> dict[CharacterMonomial, int]:
    """Return half-hyper multiplicities for external tensor products."""
    result: dict[CharacterMonomial, int] = {}
    for hyper in hypermultiplets:
        if isinstance(hyper, ProductHyperData):
            labels_by_factor = tuple(
                hyper.representations[factor.factor_id].labels
                for factor in factors
            )
        else:
            labels_by_factor = (hyper.representation.labels,)

        monomial = tuple(
            (position, labels)
            for position, labels in enumerate(labels_by_factor)
            if any(labels)
        )
        result[monomial] = result.get(monomial, 0) + hyper.number

        if hyper.kind == "full":
            conjugate = tuple(
                (
                    position,
                    conjugate_dynkin_labels(factor.algebra, labels),
                )
                for position, (factor, labels) in enumerate(
                    zip(factors, labels_by_factor, strict=True)
                )
                if any(labels)
            )
            result[conjugate] = result.get(conjugate, 0) + hyper.number

    return {monomial: value for monomial, value in result.items() if value}


def _character_basis(
    factors: tuple[GaugeFactorData, ...],
    hypermultiplets: list[HyperData | ProductHyperData],
) -> tuple[
    tuple[CharacterSpec, ...],
    tuple[int, ...],
    dict[IndexedMonomial, int],
]:
    """Return formal-character metadata for vectors and hypermultiplets."""
    matter = _matter_character_multiplicities(factors, hypermultiplets)
    vector_specs = tuple(
        (position, factor.algebra.adjoint_labels)
        for position, factor in enumerate(factors)
    )
    matter_specs = {
        specification for monomial in matter for specification in monomial
    }
    character_specs = vector_specs + tuple(
        sorted(matter_specs - set(vector_specs))
    )
    character_index = {
        specification: position
        for position, specification in enumerate(character_specs)
    }
    indexed_matter = {
        tuple(character_index[specification] for specification in monomial): value
        for monomial, value in matter.items()
    }
    vector_characters = tuple(character_index[item] for item in vector_specs)
    return character_specs, vector_characters, indexed_matter


def _build_form_program(
    order: int,
    character_count: int,
    vector_characters: tuple[int, ...],
    matter_multiplicities: dict[IndexedMonomial, int],
) -> str:
    """Build the exact FORM program for the representation-valued PE."""
    max_adams = order // 2
    derivative_order = order // 3
    character_names = ",".join(
        f"C{position}" for position in range(character_count)
    )

    letter_terms = [
        f"Kvec(t^j,y^j,u^j)*C{position}(j)"
        for position in vector_characters
    ]
    for monomial, multiplicity in sorted(matter_multiplicities.items()):
        prefix = "" if multiplicity == 1 else f"{multiplicity}*"
        characters = "".join(f"*C{position}(j)" for position in monomial)
        letter_terms.append(f"{prefix}Khyp(t^j,y^j,u^j){characters}")
    total_letters = "+".join(letter_terms)

    exponential_steps = ""
    if max_adams >= 2:
        exponential_steps = f"""#do i=2,{max_adams}
  id z=1+z*itotal/`i';
  .sort:step `i';
#enddo
"""

    return f"""#: MaxTermSize 600000
Off statistics;
S m,n,y,idx1,idx2,j,z,u,t(:{order});
CF d,{character_names};
PolyRatFun d;
Function Kvec,Khyp;

L J=sum_(idx1,0,{derivative_order},m^idx1)
   *sum_(idx2,0,{derivative_order},n^idx2);
id m=t^3*y;
id n=t^3/y;
.sort

L itotal=sum_(j,1,{max_adams},({total_letters})/j);
id Kvec(t?,y?,u?)=J*(t^2*u^2-t^4/u^2-t^3*y-t^3/y+2*t^6);
id Khyp(t?,y?,u?)=J*(t^2/u-t^4*u);
.sort

L I=z;
id z=z*itotal;
{exponential_steps}.sort

L result=1+I;
id z=1;
.sort
Print result;
.end
"""


def _run_form(
    program: str,
    *,
    form_executable: str,
    timeout: float,
) -> str:
    """Run one FORM program in an isolated writable temporary directory."""
    try:
        with tempfile.TemporaryDirectory(prefix="n2-index-form-") as directory:
            script = Path(directory) / "index.frm"
            script.write_text(program, encoding="utf-8")
            result = subprocess.run(
                [form_executable, "-q", str(script)],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"FORM executable {form_executable!r} was not found"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("FORM calculation timed out") from exc

    if result.returncode != 0 or result.stderr.strip():
        raise RuntimeError(
            f"FORM failed with code {result.returncode}: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    return result.stdout


def _split_top_level(expression: str, separator: str) -> list[str]:
    """Split on one character outside function arguments and exponent signs."""
    result: list[str] = []
    start = 0
    depth = 0
    for position, character in enumerate(expression):
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
        elif (
            character == separator
            and depth == 0
            and not (
                separator in "+-"
                and position > 0
                and expression[position - 1] == "^"
            )
        ):
            result.append(expression[start:position])
            start = position + 1
    result.append(expression[start:])
    return result


def _split_signed_terms(expression: str) -> list[str]:
    """Split a flat FORM sum while preserving each monomial's sign."""
    result: list[str] = []
    start = 0
    depth = 0
    for position, character in enumerate(expression):
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
        elif (
            position > start
            and depth == 0
            and character in "+-"
            and expression[position - 1] != "^"
        ):
            result.append(expression[start:position])
            start = position
    result.append(expression[start:])
    return [term for term in result if term]


def _canonical_character_powers(raw: dict[int, int]) -> AdamsPowers:
    """Convert a mapping from Adams operation index to power to one formal character."""
    order = sum(adams * exponent for adams, exponent in raw.items())
    return tuple(raw.get(adams, 0) for adams in range(1, order + 1))


def _parse_form_output(output: str) -> list[FormTerm]:
    """Parse FORM's exact flat polynomial without passing through floats."""
    marker = "result ="
    if marker not in output:
        raise RuntimeError(f"FORM output does not contain {marker!r}")
    expression = "".join(output.split(marker, 1)[1].split())
    if expression.endswith(";"):
        expression = expression[:-1]
    if not expression:
        raise RuntimeError("FORM returned an empty result")

    terms: list[FormTerm] = []
    for raw_term in _split_signed_terms(expression):
        sign = 1
        if raw_term.startswith("+"):
            raw_term = raw_term[1:]
        elif raw_term.startswith("-"):
            raw_term = raw_term[1:]
            sign = -1

        coefficient = Fraction(sign)
        powers = {"t": 0, "y": 0, "u": 0}
        characters: dict[int, dict[int, int]] = {}
        for factor in _split_top_level(raw_term, "*"):
            if match := _RATIONAL_RE.fullmatch(factor):
                coefficient *= Fraction(int(match.group(1)), int(match.group(2)))
            elif match := _CHARACTER_RE.fullmatch(factor):
                character = int(match.group(1))
                adams = int(match.group(2))
                exponent = int(match.group(3) or 1)
                character_powers = characters.setdefault(character, {})
                character_powers[adams] = (
                    character_powers.get(adams, 0) + exponent
                )
            elif match := _FUGACITY_RE.fullmatch(factor):
                powers[match.group(1)] += int(match.group(2) or 1)
            elif _INTEGER_RE.fullmatch(factor):
                coefficient *= int(factor)
            else:
                raise RuntimeError(
                    f"could not parse FORM factor {factor!r} in {raw_term!r}"
                )

        character_key = tuple(
            (character, _canonical_character_powers(character_powers))
            for character, character_powers in sorted(characters.items())
        )
        terms.append(
            FormTerm(
                coefficient,
                powers["t"],
                powers["y"],
                powers["u"],
                character_key,
            )
        )
    return terms


def _project_terms(
    terms: list[FormTerm],
    factors: tuple[GaugeFactorData, ...],
    character_specs: tuple[CharacterSpec, ...],
    cache: CharacterDecompositionCache,
) -> dict[tuple[int, int, int], Fraction]:
    """Project independently to the singlet of every simple gauge factor."""
    character_keys = {
        item
        for term in terms
        for item in term.characters
    }
    sorted_character_keys = sorted(character_keys)
    decomposition_requests = []
    for character, powers in sorted_character_keys:
        factor_position, labels = character_specs[character]
        algebra = factors[factor_position].algebra
        decomposition_requests.append(
            (algebra.cartan_type, labels, powers)
        )
    decompositions = dict(
        zip(
            sorted_character_keys,
            cache.get_decompositions(decomposition_requests),
            strict=True,
        )
    )

    structures = sorted({term.characters for term in terms})
    singlets_by_factor: list[
        dict[tuple[tuple[int, AdamsPowers], ...], int]
    ] = []
    for factor_position, factor in enumerate(factors):
        factor_structures = sorted(
            {
                tuple(
                    item
                    for item in structure
                    if character_specs[item[0]][0] == factor_position
                )
                for structure in structures
            }
        )
        products = [
            [decompositions[item] for item in structure]
            for structure in factor_structures
        ]
        multiplicities = cache.singlet_multiplicities(
            factor.algebra.cartan_type,
            factor.algebra.rank,
            products,
        )
        singlets_by_factor.append(
            dict(zip(factor_structures, multiplicities, strict=True))
        )

    projected: dict[tuple[int, int, int], Fraction] = {}
    for term in terms:
        singlet_multiplicity = 1
        for factor_position, singlet_by_structure in enumerate(
            singlets_by_factor
        ):
            factor_structure = tuple(
                item
                for item in term.characters
                if character_specs[item[0]][0] == factor_position
            )
            singlet_multiplicity *= singlet_by_structure[factor_structure]
        coefficient = term.coefficient * singlet_multiplicity
        key = (term.t_power, term.y_power, term.u_power)
        updated = projected.get(key, Fraction(0)) + coefficient
        if updated:
            projected[key] = updated
        else:
            projected.pop(key, None)
    return projected


def _to_sage_polynomial(
    projected: dict[tuple[int, int, int], Fraction]
) -> Any:
    """Convert projected terms to one flat Sage Laurent polynomial."""
    index_ring = INDEX_POLYNOMIAL_RING
    t, y, u = index_ring.gens()
    result = index_ring.zero()
    for (t_power, y_power, u_power), coefficient in projected.items():
        sage_coefficient = QQ(coefficient.numerator) / coefficient.denominator
        result += (
            sage_coefficient
            * t**t_power
            * y**y_power
            * u**u_power
        )
    return result


def parse_index_polynomial(value: str) -> Any:
    """Restore a serialized superconformal index as a Sage polynomial."""
    if not isinstance(value, str):
        raise TypeError("superconformal index must be a string")
    if not value.strip() or _INDEX_POLYNOMIAL_TEXT_PATTERN.fullmatch(value) is None:
        raise ValueError("invalid superconformal-index polynomial string")

    try:
        expression = sage_eval(
            value,
            locals=INDEX_POLYNOMIAL_RING.gens_dict(),
            preparse=True,
        )
        return INDEX_POLYNOMIAL_RING(expression)
    except (ArithmeticError, NameError, SyntaxError, TypeError, ValueError) as exc:
        raise ValueError(
            "invalid superconformal-index polynomial string"
        ) from exc


def calculate_index(
    data: dict[str, Any],
    order: int,
    *,
    cache_directory: str | Path | None = None,
    lie_executable: str = "lie",
    form_executable: str = "form",
    timeout: float = 600,
    processes: int | None = None,
) -> Any:
    """Calculate the exact simple- or product-group index through ``t^order``."""
    order = _as_nonnegative_int(order, "order")
    factors, hypermultiplets = _parse_input(data)

    return calculate_index_internal(
        factors,
        hypermultiplets,
        order,
        cache_directory=cache_directory,
        lie_executable=lie_executable,
        form_executable=form_executable,
        timeout=timeout,
        processes=processes,
    )


def calculate_index_internal(
    factors: tuple[GaugeFactorData, ...],
    hypermultiplets: list[HyperData | ProductHyperData],
    order: int,
    *,
    cache_directory: str | Path | None = None,
    lie_executable: str = "lie",
    form_executable: str = "form",
    timeout: float = 600,
    processes: int | None = None,
) -> Any:
    """Calculate an index from already validated internal theory data."""
    order = _as_nonnegative_int(order, "order")

    if order < 2:
        return _to_sage_polynomial({(0, 0, 0): Fraction(1)})

    character_specs, vector_characters, matter_multiplicities = _character_basis(
        factors, hypermultiplets
    )
    program = _build_form_program(
        order,
        len(character_specs),
        vector_characters,
        matter_multiplicities,
    )
    form_output = _run_form(
        program,
        form_executable=form_executable,
        timeout=timeout,
    )
    terms = _parse_form_output(form_output)
    cache = CharacterDecompositionCache(
        cache_directory,
        lie_executable=lie_executable,
        timeout=timeout,
        max_workers=processes,
    )
    projected = _project_terms(terms, factors, character_specs, cache)
    return _to_sage_polynomial(projected)


def calculate_index_from_file(
    path: str | Path,
    order: int,
    **kwargs: Any,
) -> Any:
    """Load either existing theory JSON format and calculate its index."""
    input_path = Path(path)
    with input_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return calculate_index(data, order, **kwargs)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="path to the theory JSON file")
    parser.add_argument(
        "--order",
        type=int,
        required=True,
        help="largest power of t retained in the index",
    )
    parser.add_argument(
        "--cache-directory",
        type=Path,
        help="directory for LiE character-decomposition JSON files",
    )
    parser.add_argument(
        "--processes",
        type=int,
        help="LiE cache-generation processes (default: available CPUs; 1 disables)",
    )
    args = parser.parse_args(argv)

    try:
        result = calculate_index_from_file(
            args.input,
            args.order,
            cache_directory=args.cache_directory,
            processes=args.processes,
        )
    except (
        OSError,
        json.JSONDecodeError,
        ArithmeticError,
        RuntimeError,
        ValueError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
