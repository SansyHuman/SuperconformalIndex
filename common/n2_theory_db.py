#!/usr/bin/env python3
"""Validate and store four-dimensional N=2 Lagrangian SCFTs in MySQL.

The input JSON schema is the same schema accepted by
anomalies.check_n2_anomalies.  A theory is stored only if all input and gauge
anomaly checks pass and every one-loop gauge beta function vanishes.

The database keeps theory-wide properties in shared tables and realization
data in separate Lagrangian tables.  A placeholder table for non-Lagrangian
realizations makes it possible to attach other descriptions to the same
theory later.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, is_dataclass
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

import pymysql
from pymysql.connections import Connection
from pymysql.cursors import DictCursor

if __package__:
    from .n2_theory_properties import calculate_n2_theory_properties
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.n2_theory_properties import calculate_n2_theory_properties

from anomalies.check_n2_anomalies import (
    HyperData,
    ProductHyperData,
    check_input_data,
)
from anomalies.lie_algebra import conjugate_dynkin_labels


SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_metadata (
    metadata_key VARCHAR(64) NOT NULL,
    metadata_value VARCHAR(255) NOT NULL,
    PRIMARY KEY (metadata_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS theories (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    canonical_key VARCHAR(128) NOT NULL,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_theories_canonical_key (canonical_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS theory_properties (
    theory_id BIGINT UNSIGNED NOT NULL,
    flavor_symmetry VARCHAR(255) NOT NULL,
    flavor_rank INT UNSIGNED NOT NULL,
    flavor_dimension BIGINT UNSIGNED NOT NULL,
    conformal_manifold_dimension INT UNSIGNED NULL,
    central_charges_json JSON NULL,
    coulomb_branch_spectrum_json JSON NULL,
    superconformal_indices_json JSON NULL,
    properties_json JSON NOT NULL,
    PRIMARY KEY (theory_id),
    CONSTRAINT fk_theory_properties_theory
        FOREIGN KEY (theory_id) REFERENCES theories(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS lagrangian_realizations (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    theory_id BIGINT UNSIGNED NOT NULL,
    canonical_hash CHAR(64) NOT NULL,
    gauge_group VARCHAR(255) NOT NULL,
    gauge_factor_count INT UNSIGNED NOT NULL,
    perturbative_gauge_anomaly_free BOOLEAN NOT NULL,
    global_gauge_anomaly_free BOOLEAN NOT NULL,
    anomaly_free BOOLEAN NOT NULL,
    one_loop_beta_vanishes BOOLEAN NOT NULL,
    lagrangian_scft_candidate BOOLEAN NOT NULL,
    input_json JSON NOT NULL,
    anomaly_result_json JSON NOT NULL,
    exactly_marginal_couplings_json JSON NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_lagrangian_realizations_hash (canonical_hash),
    KEY idx_lagrangian_realizations_theory (theory_id),
    CONSTRAINT fk_lagrangian_realizations_theory
        FOREIGN KEY (theory_id) REFERENCES theories(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS non_lagrangian_realizations (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    theory_id BIGINT UNSIGNED NOT NULL,
    construction_type VARCHAR(255) NOT NULL,
    source_reference TEXT NULL,
    data_json JSON NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_non_lagrangian_realizations_theory (theory_id),
    CONSTRAINT fk_non_lagrangian_realizations_theory
        FOREIGN KEY (theory_id) REFERENCES theories(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS gauge_factors (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    lagrangian_realization_id BIGINT UNSIGNED NOT NULL,
    factor_order INT UNSIGNED NOT NULL,
    factor_key VARCHAR(255) NOT NULL,
    group_name VARCHAR(255) NOT NULL,
    cartan_type VARCHAR(16) NOT NULL,
    lie_rank INT UNSIGNED NOT NULL,
    vector_beta_numerator DECIMAL(65, 0) NOT NULL,
    vector_beta_denominator DECIMAL(65, 0) UNSIGNED NOT NULL,
    matter_beta_numerator DECIMAL(65, 0) NOT NULL,
    matter_beta_denominator DECIMAL(65, 0) UNSIGNED NOT NULL,
    b0_numerator DECIMAL(65, 0) NOT NULL,
    b0_denominator DECIMAL(65, 0) UNSIGNED NOT NULL,
    one_loop_beta_vanishes BOOLEAN NOT NULL,
    witten_anomaly_parity TINYINT UNSIGNED NULL,
    global_gauge_anomaly_free BOOLEAN NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_gauge_factors_order (
        lagrangian_realization_id, factor_order
    ),
    UNIQUE KEY uq_gauge_factors_key (
        lagrangian_realization_id, factor_key
    ),
    CONSTRAINT fk_gauge_factors_realization
        FOREIGN KEY (lagrangian_realization_id)
        REFERENCES lagrangian_realizations(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS hypermultiplets (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    lagrangian_realization_id BIGINT UNSIGNED NOT NULL,
    hyper_order INT UNSIGNED NOT NULL,
    name VARCHAR(255) NOT NULL,
    kind ENUM('full', 'half') NOT NULL,
    multiplicity BIGINT UNSIGNED NOT NULL,
    total_dimension DECIMAL(65, 0) UNSIGNED NOT NULL,
    reality ENUM('real', 'pseudoreal', 'complex') NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_hypermultiplets_order (
        lagrangian_realization_id, hyper_order
    ),
    CONSTRAINT fk_hypermultiplets_realization
        FOREIGN KEY (lagrangian_realization_id)
        REFERENCES lagrangian_realizations(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS hypermultiplet_representations (
    hypermultiplet_id BIGINT UNSIGNED NOT NULL,
    gauge_factor_id BIGINT UNSIGNED NOT NULL,
    representation_name VARCHAR(255) NOT NULL,
    dynkin_labels_json JSON NOT NULL,
    dimension DECIMAL(65, 0) UNSIGNED NOT NULL,
    dynkin_index_numerator DECIMAL(65, 0) NOT NULL,
    dynkin_index_denominator DECIMAL(65, 0) UNSIGNED NOT NULL,
    reality ENUM('real', 'pseudoreal', 'complex') NOT NULL,
    beta_contribution_numerator DECIMAL(65, 0) NOT NULL,
    beta_contribution_denominator DECIMAL(65, 0) UNSIGNED NOT NULL,
    PRIMARY KEY (hypermultiplet_id, gauge_factor_id),
    CONSTRAINT fk_hyper_representations_hyper
        FOREIGN KEY (hypermultiplet_id)
        REFERENCES hypermultiplets(id) ON DELETE CASCADE,
    CONSTRAINT fk_hyper_representations_gauge_factor
        FOREIGN KEY (gauge_factor_id)
        REFERENCES gauge_factors(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS flavor_symmetry_factors (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    theory_id BIGINT UNSIGNED NOT NULL,
    factor_order INT UNSIGNED NOT NULL,
    group_name VARCHAR(255) NOT NULL,
    lie_algebra VARCHAR(255) NOT NULL,
    lie_rank INT UNSIGNED NOT NULL,
    dimension BIGINT UNSIGNED NOT NULL,
    representation_reality
        ENUM('real', 'pseudoreal', 'complex') NOT NULL,
    full_hypermultiplets BIGINT UNSIGNED NOT NULL,
    half_hypermultiplets BIGINT UNSIGNED NOT NULL,
    half_hyper_units BIGINT UNSIGNED NOT NULL,
    gauge_representation_json JSON NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_flavor_symmetry_factors_order (theory_id, factor_order),
    CONSTRAINT fk_flavor_symmetry_factors_theory
        FOREIGN KEY (theory_id) REFERENCES theories(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS exactly_marginal_couplings (
    lagrangian_realization_id BIGINT UNSIGNED NOT NULL,
    coupling_order INT UNSIGNED NOT NULL,
    gauge_factor_key VARCHAR(255) NOT NULL,
    PRIMARY KEY (lagrangian_realization_id, coupling_order),
    CONSTRAINT fk_exactly_marginal_couplings_realization
        FOREIGN KEY (lagrangian_realization_id)
        REFERENCES lagrangian_realizations(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""


class TheoryCheckError(ValueError):
    """Raised when an input is not a consistent conformal Lagrangian theory."""


@dataclass(frozen=True)
class StoredTheory:
    """Identifiers returned after a successful database import."""

    theory_id: int
    lagrangian_realization_id: int
    inserted: bool
    name: str
    gauge_group: str
    canonical_hash: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _execute(
    connection: Connection, statement: str, parameters: tuple[Any, ...] = ()
) -> int:
    with connection.cursor() as cursor:
        return cursor.execute(statement, parameters)


def _fetchone(
    connection: Connection, statement: str, parameters: tuple[Any, ...] = ()
) -> dict[str, Any] | None:
    with connection.cursor(DictCursor) as cursor:
        cursor.execute(statement, parameters)
        return cursor.fetchone()


def _insert(
    connection: Connection, statement: str, parameters: tuple[Any, ...]
) -> int:
    with connection.cursor() as cursor:
        cursor.execute(statement, parameters)
        if cursor.lastrowid is None:
            raise ArithmeticError("MySQL did not return an inserted row id")
        return int(cursor.lastrowid)


def initialize_database(connection: Connection) -> None:
    """Create the version-one MySQL schema on an open connection."""
    for statement in SCHEMA_SQL.split(";"):
        if statement.strip():
            _execute(connection, statement)

    version = _fetchone(
        connection,
        """
        SELECT metadata_value
        FROM schema_metadata
        WHERE metadata_key = %s
        """,
        ("schema_version",),
    )
    if version is None:
        _execute(
            connection,
            """
            INSERT INTO schema_metadata(metadata_key, metadata_value)
            VALUES (%s, %s)
            """,
            ("schema_version", str(SCHEMA_VERSION)),
        )
    elif int(version["metadata_value"]) != SCHEMA_VERSION:
        raise RuntimeError(
            "unsupported database schema version "
            f"{version['metadata_value']}; expected {SCHEMA_VERSION}"
        )


def connect_database(
    database: str,
    *,
    host: str = "127.0.0.1",
    port: int = 3306,
    user: str = "root",
    password: str = "",
    unix_socket: str | None = None,
    connect_timeout: int = 10,
) -> Connection:
    """Connect to an existing MySQL database and initialize its tables."""
    connection = pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        unix_socket=unix_socket,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=True,
        connect_timeout=connect_timeout,
    )
    try:
        initialize_database(connection)
    except BaseException:
        connection.close()
        raise
    return connection


def _json_default(value: Any) -> Any:
    if isinstance(value, Fraction):
        return {
            "numerator": value.numerator,
            "denominator": value.denominator,
        }
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, tuple):
        return list(value)
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def _json_text(value: Any, *, canonical: bool = False) -> str:
    return json.dumps(
        value,
        default=_json_default,
        ensure_ascii=False,
        sort_keys=canonical,
        separators=(",", ":") if canonical else None,
    )


def _optional_json_text(value: Any) -> str | None:
    return None if value is None else _json_text(value)


def _fraction_parts(value: Fraction | int) -> tuple[int, int]:
    fraction = Fraction(value)
    return fraction.numerator, fraction.denominator


def _factor_rows(anomaly_result: dict[str, Any]) -> list[dict[str, Any]]:
    if "gauge_factors" in anomaly_result:
        return anomaly_result["gauge_factors"]
    return [
        {
            "id": "gauge",
            "group": anomaly_result["group"],
            "algebra": anomaly_result["algebra"],
            "rank": anomaly_result["rank"],
            "vector_beta_contribution": anomaly_result[
                "vector_beta_contribution"
            ],
            "matter_beta_contribution": anomaly_result[
                "matter_beta_contribution"
            ],
            "b0": anomaly_result["b0"],
            "one_loop_beta_vanishes": anomaly_result[
                "one_loop_beta_vanishes"
            ],
            "witten_anomaly_parity": anomaly_result["witten_anomaly_parity"],
            "global_gauge_anomaly_free": anomaly_result[
                "global_gauge_anomaly_free"
            ],
        }
    ]


def _canonical_representation(
    factor_rows: list[dict[str, Any]],
    representations: dict[str, Any],
) -> tuple[tuple[int, ...], ...]:
    labels = tuple(
        tuple(representations[factor["id"]].labels) for factor in factor_rows
    )
    conjugate = tuple(
        conjugate_dynkin_labels(factor["algebra"], factor_labels)
        for factor, factor_labels in zip(factor_rows, labels)
    )
    return min(labels, conjugate)


def _canonical_lagrangian_payload(
    anomaly_result: dict[str, Any],
) -> dict[str, Any]:
    factor_rows = _factor_rows(anomaly_result)
    aggregated: dict[tuple[str, tuple[tuple[int, ...], ...]], int] = {}

    if "gauge_factors" in anomaly_result:
        hypers: list[ProductHyperData] = anomaly_result["hypermultiplets"]
        for hyper in hypers:
            if hyper.number == 0:
                continue
            labels = _canonical_representation(
                factor_rows, hyper.representations
            )
            key = (hyper.kind, labels)
            aggregated[key] = aggregated.get(key, 0) + hyper.number
    else:
        hypers: list[HyperData] = anomaly_result["hypermultiplets"]
        algebra = factor_rows[0]["algebra"]
        for hyper in hypers:
            if hyper.number == 0:
                continue
            labels = tuple(hyper.representation.labels)
            conjugate = conjugate_dynkin_labels(algebra, labels)
            key = (hyper.kind, (min(labels, conjugate),))
            aggregated[key] = aggregated.get(key, 0) + hyper.number

    canonical_hypers = [
        {
            "kind": kind,
            "dynkin_labels": [list(labels) for labels in representation],
            "number": number,
        }
        for (kind, representation), number in sorted(aggregated.items())
    ]
    return {
        "gauge_algebras": [factor["algebra"] for factor in factor_rows],
        "hypermultiplets": canonical_hypers,
    }


def _canonical_hash(anomaly_result: dict[str, Any]) -> str:
    payload = _json_text(
        _canonical_lagrangian_payload(anomaly_result), canonical=True
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _shared_properties(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "flavor_symmetry": properties["flavor_symmetry"],
        "conformal_manifold_dimension": properties[
            "conformal_manifold_dimension"
        ],
        "central_charges": properties["central_charges"],
        "coulomb_branch_spectrum": properties[
            "coulomb_branch_spectrum"
        ],
        "superconformal_indices": properties["superconformal_indices"],
    }


def _checked_results(
    data: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    anomaly_result = check_input_data(data)
    if anomaly_result["errors"]:
        raise TheoryCheckError(
            "invalid theory input: " + "; ".join(anomaly_result["errors"])
        )
    if not anomaly_result["anomaly_free"]:
        raise TheoryCheckError("the theory is not gauge-anomaly-free")
    if not anomaly_result["one_loop_beta_vanishes"]:
        raise TheoryCheckError(
            "the theory is not conformal: at least one one-loop gauge beta "
            "function does not vanish"
        )
    if not anomaly_result["lagrangian_scft_candidate"]:
        raise TheoryCheckError(
            "the theory does not pass the Lagrangian SCFT-candidate checks"
        )

    properties = calculate_n2_theory_properties(data)
    if not properties["lagrangian_scft_candidate"]:
        raise ArithmeticError(
            "the anomaly checker and property calculator disagree"
        )
    return anomaly_result, properties


def _insert_theory(
    connection: Connection,
    canonical_hash: str,
    name: str,
    theory_id: int | None,
) -> int:
    if theory_id is not None:
        row = _fetchone(
            connection,
            "SELECT id FROM theories WHERE id = %s",
            (theory_id,),
        )
        if row is None:
            raise ValueError(f"unknown theory id {theory_id}")
        return theory_id

    return _insert(
        connection,
        """
        INSERT INTO theories(canonical_key, name)
        VALUES (%s, %s)
        """,
        (f"lagrangian:{canonical_hash}", name),
    )


def _insert_shared_properties(
    connection: Connection,
    theory_id: int,
    properties: dict[str, Any],
) -> None:
    shared = _shared_properties(properties)
    serialized = _json_text(shared, canonical=True)
    existing = _fetchone(
        connection,
        "SELECT properties_json FROM theory_properties WHERE theory_id = %s",
        (theory_id,),
    )
    if existing is not None:
        existing_properties = existing["properties_json"]
        if isinstance(existing_properties, str):
            existing_properties = json.loads(existing_properties)
        if existing_properties != shared:
            raise ValueError(
                f"theory {theory_id} already has different shared properties"
            )
        return

    flavor = properties["flavor_symmetry"]
    _execute(
        connection,
        """
        INSERT INTO theory_properties(
            theory_id,
            flavor_symmetry,
            flavor_rank,
            flavor_dimension,
            conformal_manifold_dimension,
            central_charges_json,
            coulomb_branch_spectrum_json,
            superconformal_indices_json,
            properties_json
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            theory_id,
            flavor["connected_group"],
            flavor["rank"],
            flavor["dimension"],
            properties["conformal_manifold_dimension"],
            _optional_json_text(properties["central_charges"]),
            _optional_json_text(properties["coulomb_branch_spectrum"]),
            _optional_json_text(properties["superconformal_indices"]),
            serialized,
        ),
    )
    for order, factor in enumerate(flavor["factors"]):
        _execute(
            connection,
            """
            INSERT INTO flavor_symmetry_factors(
                theory_id,
                factor_order,
                group_name,
                lie_algebra,
                lie_rank,
                dimension,
                representation_reality,
                full_hypermultiplets,
                half_hypermultiplets,
                half_hyper_units,
                gauge_representation_json
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                theory_id,
                order,
                factor["group"],
                factor["lie_algebra"],
                factor["rank"],
                factor["dimension"],
                factor["representation_reality"],
                factor["full_hypermultiplets"],
                factor["half_hypermultiplets"],
                factor["half_hyper_units"],
                _json_text(factor["gauge_representation"]),
            ),
        )


def _insert_realization(
    connection: Connection,
    theory_id: int,
    canonical_hash: str,
    data: dict[str, Any],
    anomaly_result: dict[str, Any],
    properties: dict[str, Any],
) -> int:
    factor_rows = _factor_rows(anomaly_result)
    realization_id = _insert(
        connection,
        """
        INSERT INTO lagrangian_realizations(
            theory_id,
            canonical_hash,
            gauge_group,
            gauge_factor_count,
            perturbative_gauge_anomaly_free,
            global_gauge_anomaly_free,
            anomaly_free,
            one_loop_beta_vanishes,
            lagrangian_scft_candidate,
            input_json,
            anomaly_result_json,
            exactly_marginal_couplings_json
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            theory_id,
            canonical_hash,
            anomaly_result["group"],
            len(factor_rows),
            int(anomaly_result["perturbative_gauge_anomaly_free"]),
            int(anomaly_result["global_gauge_anomaly_free"]),
            int(anomaly_result["anomaly_free"]),
            int(anomaly_result["one_loop_beta_vanishes"]),
            int(anomaly_result["lagrangian_scft_candidate"]),
            _json_text(data, canonical=True),
            _json_text(anomaly_result),
            _json_text(properties["exactly_marginal_gauge_couplings"]),
        ),
    )

    gauge_factor_ids: dict[str, int] = {}
    for order, factor in enumerate(factor_rows):
        vector_numerator, vector_denominator = _fraction_parts(
            factor["vector_beta_contribution"]
        )
        matter_numerator, matter_denominator = _fraction_parts(
            factor["matter_beta_contribution"]
        )
        b0_numerator, b0_denominator = _fraction_parts(factor["b0"])
        gauge_factor_id = _insert(
            connection,
            """
            INSERT INTO gauge_factors(
                lagrangian_realization_id,
                factor_order,
                factor_key,
                group_name,
                cartan_type,
                lie_rank,
                vector_beta_numerator,
                vector_beta_denominator,
                matter_beta_numerator,
                matter_beta_denominator,
                b0_numerator,
                b0_denominator,
                one_loop_beta_vanishes,
                witten_anomaly_parity,
                global_gauge_anomaly_free
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s
            )
            """,
            (
                realization_id,
                order,
                factor["id"],
                factor["group"],
                factor["algebra"],
                factor["rank"],
                vector_numerator,
                vector_denominator,
                matter_numerator,
                matter_denominator,
                b0_numerator,
                b0_denominator,
                int(factor["one_loop_beta_vanishes"]),
                factor["witten_anomaly_parity"],
                int(factor["global_gauge_anomaly_free"]),
            ),
        )
        gauge_factor_ids[factor["id"]] = gauge_factor_id

    if "gauge_factors" in anomaly_result:
        product_hypers: list[ProductHyperData] = anomaly_result[
            "hypermultiplets"
        ]
        for order, hyper in enumerate(product_hypers):
            hyper_id = _insert(
                connection,
                """
                INSERT INTO hypermultiplets(
                    lagrangian_realization_id,
                    hyper_order,
                    name,
                    kind,
                    multiplicity,
                    total_dimension,
                    reality
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    realization_id,
                    order,
                    hyper.name,
                    hyper.kind,
                    hyper.number,
                    hyper.dimension,
                    hyper.reality,
                ),
            )
            for factor in factor_rows:
                factor_key = factor["id"]
                _insert_hyper_representation(
                    connection,
                    hyper_id,
                    gauge_factor_ids[factor_key],
                    hyper.representations[factor_key],
                    hyper.beta_contributions[factor_key],
                )
    else:
        simple_hypers: list[HyperData] = anomaly_result["hypermultiplets"]
        gauge_factor_id = gauge_factor_ids["gauge"]
        for order, hyper in enumerate(simple_hypers):
            representation = hyper.representation
            hyper_id = _insert(
                connection,
                """
                INSERT INTO hypermultiplets(
                    lagrangian_realization_id,
                    hyper_order,
                    name,
                    kind,
                    multiplicity,
                    total_dimension,
                    reality
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    realization_id,
                    order,
                    representation.name,
                    hyper.kind,
                    hyper.number,
                    representation.dimension,
                    representation.reality,
                ),
            )
            _insert_hyper_representation(
                connection,
                hyper_id,
                gauge_factor_id,
                representation,
                hyper.beta_contribution,
            )

    for order, factor_key in enumerate(
        properties["exactly_marginal_gauge_couplings"]
    ):
        _execute(
            connection,
            """
            INSERT INTO exactly_marginal_couplings(
                lagrangian_realization_id,
                coupling_order,
                gauge_factor_key
            )
            VALUES (%s, %s, %s)
            """,
            (realization_id, order, factor_key),
        )
    return realization_id


def _insert_hyper_representation(
    connection: Connection,
    hyper_id: int,
    gauge_factor_id: int,
    representation: Any,
    beta_contribution: Fraction,
) -> None:
    index_numerator, index_denominator = _fraction_parts(
        representation.dynkin_index
    )
    beta_numerator, beta_denominator = _fraction_parts(beta_contribution)
    _execute(
        connection,
        """
        INSERT INTO hypermultiplet_representations(
            hypermultiplet_id,
            gauge_factor_id,
            representation_name,
            dynkin_labels_json,
            dimension,
            dynkin_index_numerator,
            dynkin_index_denominator,
            reality,
            beta_contribution_numerator,
            beta_contribution_denominator
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            hyper_id,
            gauge_factor_id,
            representation.name,
            _json_text(list(representation.labels)),
            representation.dimension,
            index_numerator,
            index_denominator,
            representation.reality,
            beta_numerator,
            beta_denominator,
        ),
    )


def store_lagrangian_theory(
    connection: Connection,
    data: dict[str, Any],
    *,
    name: str | None = None,
    theory_id: int | None = None,
) -> StoredTheory:
    """Check a theory and atomically store its properties and realization.

    Reimporting the same normalized Lagrangian realization is idempotent.  Set
    theory_id to attach a new realization, such as a dual description, to an
    existing shared theory record.
    """
    initialize_database(connection)
    anomaly_result, properties = _checked_results(data)
    canonical_hash = _canonical_hash(anomaly_result)

    existing = _fetchone(
        connection,
        """
        SELECT
            lr.id AS realization_id,
            lr.theory_id,
            lr.gauge_group,
            t.name
        FROM lagrangian_realizations AS lr
        JOIN theories AS t ON t.id = lr.theory_id
        WHERE lr.canonical_hash = %s
        """,
        (canonical_hash,),
    )
    if existing is not None:
        if theory_id is not None and theory_id != existing["theory_id"]:
            raise ValueError(
                "this Lagrangian realization is already attached to theory "
                f"{existing['theory_id']}"
            )
        return StoredTheory(
            theory_id=int(existing["theory_id"]),
            lagrangian_realization_id=int(existing["realization_id"]),
            inserted=False,
            name=str(existing["name"]),
            gauge_group=str(existing["gauge_group"]),
            canonical_hash=canonical_hash,
        )

    theory_name = (
        name.strip()
        if name is not None and name.strip()
        else f"{anomaly_result['group']} Lagrangian SCFT"
    )
    connection.begin()
    try:
        stored_theory_id = _insert_theory(
            connection, canonical_hash, theory_name, theory_id
        )
        _insert_shared_properties(connection, stored_theory_id, properties)
        realization_id = _insert_realization(
            connection,
            stored_theory_id,
            canonical_hash,
            data,
            anomaly_result,
            properties,
        )
        _execute(
            connection,
            """
            UPDATE theories
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (stored_theory_id,),
        )
    except BaseException:
        connection.rollback()
        raise
    else:
        connection.commit()

    stored_row = _fetchone(
        connection,
        "SELECT name FROM theories WHERE id = %s",
        (stored_theory_id,),
    )
    if stored_row is None:
        raise ArithmeticError("stored theory disappeared after commit")
    return StoredTheory(
        theory_id=stored_theory_id,
        lagrangian_realization_id=realization_id,
        inserted=True,
        name=str(stored_row["name"]),
        gauge_group=anomaly_result["group"],
        canonical_hash=canonical_hash,
    )


def store_lagrangian_theory_from_file(
    database: str,
    input_path: str | Path,
    *,
    name: str | None = None,
    theory_id: int | None = None,
    host: str = "127.0.0.1",
    port: int = 3306,
    user: str = "root",
    password: str = "",
    unix_socket: str | None = None,
    connect_timeout: int = 10,
) -> StoredTheory:
    """Load a JSON file and store a passing theory in MySQL."""
    with Path(input_path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    connection = connect_database(
        database,
        host=host,
        port=port,
        user=user,
        password=password,
        unix_socket=unix_socket,
        connect_timeout=connect_timeout,
    )
    try:
        return store_lagrangian_theory(
            connection, data, name=name, theory_id=theory_id
        )
    finally:
        connection.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="anomaly-checker JSON file")
    parser.add_argument("database", help="name of an existing MySQL database")
    parser.add_argument("--name", help="display name for a newly created theory")
    parser.add_argument(
        "--host",
        default=os.environ.get("N2_DB_HOST", "127.0.0.1"),
        help="MySQL server host (default: N2_DB_HOST or 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=3306,
        help="MySQL server port (default: 3306)",
    )
    parser.add_argument(
        "--user",
        default=os.environ.get("N2_DB_USER", "root"),
        help="MySQL user (default: N2_DB_USER or root)",
    )
    parser.add_argument(
        "--unix-socket",
        default=os.environ.get("N2_DB_UNIX_SOCKET"),
        help="optional MySQL Unix socket path",
    )
    parser.add_argument(
        "--connect-timeout",
        type=int,
        default=10,
        help="connection timeout in seconds (default: 10)",
    )
    parser.add_argument(
        "--theory-id",
        type=int,
        help="attach the realization to an existing theory id",
    )
    args = parser.parse_args(argv)
    try:
        result = store_lagrangian_theory_from_file(
            args.database,
            args.input,
            name=args.name,
            theory_id=args.theory_id,
            host=args.host,
            port=args.port,
            user=args.user,
            password=os.environ.get("N2_DB_PASSWORD", ""),
            unix_socket=args.unix_socket,
            connect_timeout=args.connect_timeout,
        )
    except TheoryCheckError as exc:
        print(f"Rejected: {exc}", file=sys.stderr)
        return 1
    except (
        OSError,
        json.JSONDecodeError,
        ValueError,
        ArithmeticError,
        pymysql.MySQLError,
        RuntimeError,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result.as_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
