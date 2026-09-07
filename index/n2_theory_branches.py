#!/usr/bin/env python3
"""Calculate the Coulomb-branch limit of a four-dimensional N=2 index.

There are two supported inputs:

* A Coulomb-branch spectrum.  Its truncated Hilbert series is evaluated as
  the plethystic exponential with FORM.  Rational scaling dimensions are
  supported by performing the FORM calculation in an integer-rescaled
  auxiliary fugacity and converting the answer to a Sage Puiseux series.
* An already calculated full index in the project's ``(t, y, u)``
  convention.  The Coulomb limit keeps ``x = t^2*u^2`` fixed, so a monomial
  ``t^a*y^b*u^c`` survives precisely when ``a == c``.  The surviving result
  is required to be independent of ``y`` and is mapped to ``x^(c/2)``.

For a Lagrangian theory, :func:`calculate_lagrangian_coulomb_branch_index`
accepts one or more :class:`GaugeFactorData` objects and obtains the spectrum
from the degrees of the gauge algebras' basic Weyl-invariant polynomials.

The lower-level :func:`calculate_plethystic_exponential` also accepts signed
coefficients.  It can therefore be reused when a future non-Lagrangian
implementation supplies generators and relations rather than a freely
generated Coulomb-branch spectrum.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from fractions import Fraction
from functools import lru_cache
from math import lcm
import re
from typing import Any

from sage.all import PuiseuxSeriesRing, QQ, WeylGroup

from anomalies.check_n2_anomalies import GaugeFactorData
from common.form_utils import run_form, split_signed_terms, split_top_level
from common.number_utils import (
    as_integer,
    as_nonnegative_fraction,
    as_positive_fraction,
)
from index.n2_theory_index import (
    INDEX_POLYNOMIAL_RING,
    parse_index_polynomial,
)


COULOMB_INDEX_RING = PuiseuxSeriesRing(QQ, "x")

_RATIONAL_RE = re.compile(r"d\((-?\d+),(-?\d+)\)\Z")
_POWER_RE = re.compile(r"q(?:\^(\d+))?\Z")
_INTEGER_RE = re.compile(r"\d+\Z")


def _normalize_plethystic_log(
    terms: Mapping[Any, Any],
) -> dict[Fraction, int]:
    """Validate ``dimension -> signed multiplicity`` plethystic-log terms."""
    if not isinstance(terms, Mapping):
        raise ValueError(
            "plethystic_log must map positive dimensions to integer coefficients"
        )

    result: dict[Fraction, int] = {}
    for raw_dimension, raw_coefficient in terms.items():
        dimension = as_positive_fraction(raw_dimension, "dimension")
        coefficient = as_integer(raw_coefficient, "coefficient")
        updated = result.get(dimension, 0) + coefficient
        if updated:
            result[dimension] = updated
        else:
            result.pop(dimension, None)
    return result


def _normalize_spectrum(
    spectrum: Iterable[Any] | Mapping[Any, Any],
) -> dict[Fraction, int]:
    """Convert a spectrum or multiplicity mapping to a plethystic logarithm."""
    if isinstance(spectrum, Mapping):
        normalized = _normalize_plethystic_log(spectrum)
        if any(multiplicity < 0 for multiplicity in normalized.values()):
            raise ValueError("spectrum multiplicities must be nonnegative")
        return normalized

    if isinstance(spectrum, (str, bytes)):
        raise ValueError(
            "spectrum must be an iterable of dimensions or a multiplicity mapping"
        )
    try:
        dimensions = iter(spectrum)
    except TypeError as exc:
        raise ValueError(
            "spectrum must be an iterable of dimensions or a multiplicity mapping"
        ) from exc

    result: dict[Fraction, int] = {}
    for raw_dimension in dimensions:
        dimension = as_positive_fraction(raw_dimension, "dimension")
        result[dimension] = result.get(dimension, 0) + 1
    return result


def _normalize_gauge_factors(
    gauge_factors: GaugeFactorData | Iterable[GaugeFactorData],
) -> tuple[GaugeFactorData, ...]:
    """Return a validated tuple of simple Lagrangian gauge factors."""
    if isinstance(gauge_factors, GaugeFactorData):
        return (gauge_factors,)
    if isinstance(gauge_factors, (str, bytes)):
        raise ValueError(
            "gauge_factors must contain GaugeFactorData objects"
        )
    try:
        factors = tuple(gauge_factors)
    except TypeError as exc:
        raise ValueError(
            "gauge_factors must be a GaugeFactorData object or an iterable of them"
        ) from exc
    if any(not isinstance(factor, GaugeFactorData) for factor in factors):
        raise ValueError(
            "gauge_factors must contain only GaugeFactorData objects"
        )
    return factors


@lru_cache(maxsize=None)
def _invariant_degrees(cartan_type: str) -> tuple[int, ...]:
    """Return degrees of basic Weyl-invariant polynomials for one factor."""
    return tuple(int(degree) for degree in WeylGroup(cartan_type).degrees())


def coulomb_branch_spectrum_from_gauge_factors(
    gauge_factors: GaugeFactorData | Iterable[GaugeFactorData],
) -> tuple[int, ...]:
    """Return the Lagrangian Coulomb-generator dimensions as a multiset.

    Each simple gauge factor contributes the degrees of its basic invariant
    polynomials.  The sorted tuple preserves repeated dimensions, including
    repetitions within one factor such as the two degree-four invariants of
    ``D4`` and repetitions shared by different factors.
    """
    factors = _normalize_gauge_factors(gauge_factors)
    return tuple(
        sorted(
            degree
            for factor in factors
            for degree in _invariant_degrees(factor.algebra.cartan_type)
        )
    )


def _format_form_letter(terms: Mapping[int, int], adams_symbol: str) -> str:
    """Format an integer-rescaled plethystic logarithm for FORM."""
    pieces: list[str] = []
    for degree, coefficient in sorted(terms.items()):
        power = f"q^({degree}*{adams_symbol})"
        if not pieces:
            if coefficient == -1:
                pieces.append(f"-{power}")
            elif coefficient == 1:
                pieces.append(power)
            else:
                pieces.append(f"{coefficient}*{power}")
        elif coefficient == -1:
            pieces.append(f"-{power}")
        elif coefficient < 0:
            pieces.append(f"{coefficient}*{power}")
        elif coefficient == 1:
            pieces.append(f"+{power}")
        else:
            pieces.append(f"+{coefficient}*{power}")
    return "".join(pieces) or "0"


def _build_plethystic_form_program(
    terms: Mapping[int, int], order: int
) -> str:
    """Build a FORM program for a truncated plethystic exponential."""
    minimum_degree = min(terms)
    maximum_adams = order // minimum_degree
    maximum_particles = order // minimum_degree
    letter = _format_form_letter(terms, "j")

    exponential_steps = ""
    if maximum_particles >= 2:
        exponential_steps = f"""#do k=2,{maximum_particles}
  id z=1+z*exponent/`k';
  .sort:step `k';
#enddo
"""

    return f"""#: MaxTermSize 600000
Off statistics;
S j,k,z,q(:{order});
CF d;
PolyRatFun d;

L exponent=sum_(j,1,{maximum_adams},({letter})/j);
.sort

L series=z*exponent;
{exponential_steps}.sort

L result=1+series;
id z=1;
.sort
Print result;
.end
"""


def _parse_form_series(output: str) -> dict[int, Fraction]:
    """Parse FORM's exact univariate result without passing through floats."""
    marker = "result ="
    if marker not in output:
        raise RuntimeError(f"FORM output does not contain {marker!r}")
    expression = "".join(output.split(marker, 1)[1].split())
    if expression.endswith(";"):
        expression = expression[:-1]
    if not expression:
        raise RuntimeError("FORM returned an empty Coulomb-index result")

    result: dict[int, Fraction] = {}
    for raw_term in split_signed_terms(expression):
        sign = 1
        if raw_term.startswith("+"):
            raw_term = raw_term[1:]
        elif raw_term.startswith("-"):
            raw_term = raw_term[1:]
            sign = -1

        coefficient = Fraction(sign)
        power = 0
        for factor in split_top_level(raw_term, "*"):
            if match := _RATIONAL_RE.fullmatch(factor):
                coefficient *= Fraction(int(match.group(1)), int(match.group(2)))
            elif match := _POWER_RE.fullmatch(factor):
                power += int(match.group(1) or 1)
            elif _INTEGER_RE.fullmatch(factor):
                coefficient *= int(factor)
            else:
                raise RuntimeError(
                    f"could not parse FORM factor {factor!r} in {raw_term!r}"
                )

        updated = result.get(power, Fraction(0)) + coefficient
        if updated:
            result[power] = updated
        else:
            result.pop(power, None)
    return result


def _to_coulomb_series(
    terms: Mapping[Fraction, Fraction],
) -> Any:
    """Convert exact ``x`` powers and coefficients to one Sage Puiseux series."""
    x = COULOMB_INDEX_RING.gen()
    result = COULOMB_INDEX_RING.zero()
    for dimension, coefficient in sorted(terms.items()):
        sage_coefficient = QQ(coefficient.numerator) / coefficient.denominator
        sage_dimension = QQ(dimension.numerator) / dimension.denominator
        result += sage_coefficient * x**sage_dimension
    return result


def calculate_plethystic_exponential(
    plethystic_log: Mapping[Any, Any],
    max_dimension: Any,
    *,
    form_executable: str = "form",
    timeout: float = 600,
) -> Any:
    """Calculate a truncated exact plethystic exponential with FORM.

    ``plethystic_log`` maps positive rational dimensions to signed integer
    coefficients.  Positive coefficients describe generators and negative
    coefficients can describe relations.  The returned Sage Puiseux series
    contains every term of dimension at most ``max_dimension``.
    """
    maximum = as_nonnegative_fraction(max_dimension, "max_dimension")
    normalized = {
        dimension: coefficient
        for dimension, coefficient in _normalize_plethystic_log(
            plethystic_log
        ).items()
        if dimension <= maximum
    }
    if not normalized or maximum == 0:
        return _to_coulomb_series({Fraction(0): Fraction(1)})

    scale = lcm(
        maximum.denominator,
        *(dimension.denominator for dimension in normalized),
    )
    scaled_order = (maximum * scale).numerator
    scaled_terms = {
        (dimension * scale).numerator: coefficient
        for dimension, coefficient in normalized.items()
    }
    program = _build_plethystic_form_program(scaled_terms, scaled_order)
    output = run_form(
        program,
        form_executable=form_executable,
        timeout=timeout,
    )
    form_terms = _parse_form_series(output)
    physical_terms = {
        Fraction(power, scale): coefficient
        for power, coefficient in form_terms.items()
    }
    return _to_coulomb_series(physical_terms)


def calculate_coulomb_branch_index_from_full_index(
    full_index: Any,
    *,
    max_dimension: Any | None = None,
) -> Any:
    """Take the Coulomb limit of a full index in the ``(t, y, u)`` ring."""
    if isinstance(full_index, str):
        polynomial = parse_index_polynomial(full_index)
    else:
        try:
            polynomial = INDEX_POLYNOMIAL_RING(full_index)
        except (ArithmeticError, TypeError, ValueError) as exc:
            raise ValueError(
                "full_index must be a polynomial in the project's t, y, u ring"
            ) from exc

    maximum = (
        None
        if max_dimension is None
        else as_nonnegative_fraction(max_dimension, "max_dimension")
    )
    result: dict[Fraction, Fraction] = {}
    for powers, sage_coefficient in polynomial.dict().items():
        t_power, y_power, u_power = map(int, powers)
        coefficient = Fraction(str(sage_coefficient))

        if t_power < u_power:
            raise ValueError(
                "full_index has a monomial that diverges in the Coulomb limit: "
                f"t^{t_power}*y^{y_power}*u^{u_power}"
            )
        if t_power != u_power:
            continue
        if y_power != 0:
            raise ValueError(
                "the Coulomb-limit terms of full_index must be independent of y"
            )

        dimension = Fraction(u_power, 2)
        if dimension < 0:
            raise ValueError(
                "full_index has a negative-dimension term in the Coulomb limit"
            )
        if maximum is not None and dimension > maximum:
            continue

        updated = result.get(dimension, Fraction(0)) + coefficient
        if updated:
            result[dimension] = updated
        else:
            result.pop(dimension, None)
    return _to_coulomb_series(result)


def calculate_lagrangian_coulomb_branch_index(
    gauge_factors: GaugeFactorData | Iterable[GaugeFactorData],
    max_dimension: Any,
    *,
    form_executable: str = "form",
    timeout: float = 600,
) -> Any:
    """Calculate a Lagrangian Coulomb index from simple gauge-factor data.

    Matter data is unnecessary: the Coulomb generators are the basic
    invariant polynomials of each simple gauge algebra.  Their degrees are
    passed to the same FORM plethystic calculation used for an explicit
    spectrum.
    """
    spectrum = coulomb_branch_spectrum_from_gauge_factors(gauge_factors)
    return calculate_coulomb_branch_index(
        spectrum,
        max_dimension,
        form_executable=form_executable,
        timeout=timeout,
    )


def calculate_coulomb_branch_index(
    spectrum: Iterable[Any] | Mapping[Any, Any] | None = None,
    max_dimension: Any | None = None,
    *,
    full_index: Any | None = None,
    form_executable: str = "form",
    timeout: float = 600,
) -> Any:
    """Calculate a Coulomb-branch index from exactly one supported source.

    Supply either ``spectrum`` or ``full_index``.  A spectrum may be an
    iterable of positive rational dimensions, or a mapping from dimensions
    to nonnegative integer multiplicities.  Spectrum input requires
    ``max_dimension`` and is evaluated with FORM.  A full index may be either
    the Sage polynomial returned by :func:`index.n2_theory_index.calculate_index`
    or its serialized string; ``max_dimension`` is optional for this source.
    """
    if (spectrum is None) == (full_index is None):
        raise ValueError("supply exactly one of spectrum or full_index")

    if full_index is not None:
        return calculate_coulomb_branch_index_from_full_index(
            full_index,
            max_dimension=max_dimension,
        )

    if max_dimension is None:
        raise ValueError("max_dimension is required for spectrum input")
    assert spectrum is not None
    plethystic_log = _normalize_spectrum(spectrum)
    return calculate_plethystic_exponential(
        plethystic_log,
        max_dimension,
        form_executable=form_executable,
        timeout=timeout,
    )
