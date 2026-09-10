"""Measure the current FORM cache using an existing entry and disposable databases.

Run with Sage's Python; the source database is opened read-only. Timings exclude
FORM execution and parsing, and leave Python's garbage collector enabled.
"""

import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import re
import sqlite3
import statistics
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from index.form_expansion_cache import FormExpansionCache


INSERT = """INSERT INTO form_expansions (program, expansion_json)
            VALUES (?, ?) ON CONFLICT (program) DO NOTHING"""
SELECT = "SELECT expansion_json FROM form_expansions WHERE program=?"


def timed(operation):
    start = time.perf_counter_ns()
    value = operation()
    return value, (time.perf_counter_ns() - start) / 1_000_000


def summarize(samples):
    ordered = sorted(samples)

    def percentile(fraction):
        position = (len(ordered) - 1) * fraction
        low = int(position)
        high = min(low + 1, len(ordered) - 1)
        return ordered[low] + (ordered[high] - ordered[low]) * (position - low)

    return {
        "median_ms": statistics.median(samples),
        "p10_ms": percentile(0.1),
        "p90_ms": percentile(0.9),
        "min_ms": min(samples),
        "max_ms": max(samples),
        "samples_ms": samples,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "form_expansion_cache.db")
    parser.add_argument("--repeats", type=int, default=30)
    parser.add_argument("--warmups", type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 1 or args.warmups < 0:
        parser.error("repeats must be positive and warmups nonnegative")

    with closing(sqlite3.connect(args.source.resolve().as_uri() + "?mode=ro", uri=True)) as source:
        program, payload = source.execute(
            "SELECT program, expansion_json FROM form_expansions "
            "ORDER BY length(expansion_json) DESC LIMIT 1"
        ).fetchone()
    terms = FormExpansionCache._decode_expansion(payload)
    assert FormExpansionCache._encode_expansion(terms) == payload
    print(f"Sample: {len(terms):,} terms; {len(payload.encode('utf-8')):,} JSON bytes", flush=True)

    samples = {name: [] for name in (
        "initialize_empty_database", "serialize", "insert_and_commit", "save_total",
        "select_and_fetch", "deserialize", "load_breakdown_total",
        "get_expansion_existing_connection", "get_expansion_new_connection",
    )}

    # The disposable files are beside the report, on the project's filesystem.
    # Each timed insert writes one actual row into a fresh initialized database;
    # it never measures the ON CONFLICT no-op case.
    with tempfile.TemporaryDirectory(prefix=".timing-", dir=Path(__file__).parent) as tmp:
        for iteration in range(args.warmups + args.repeats):
            path = Path(tmp) / "expansion.db"
            with FormExpansionCache(database_path=path) as cache:
                connection, initialize_ms = timed(cache._connection)
                encoded, serialize_ms = timed(lambda: cache._encode_expansion(terms))

                def write():
                    with connection:
                        connection.execute(INSERT, (program, encoded))

                _, insert_ms = timed(lambda: cache._retry_busy(write))
                pragmas = {
                    name: connection.execute(f"PRAGMA {name}").fetchone()[0]
                    for name in ("journal_mode", "synchronous", "wal_autocheckpoint", "page_size")
                }
                row = connection.execute(SELECT, (program,)).fetchone()
                assert row[0] == payload
                assert connection.execute("SELECT count(*) FROM form_expansions").fetchone()[0] == 1

            if iteration >= args.warmups:
                samples["initialize_empty_database"].append(initialize_ms)
                samples["serialize"].append(serialize_ms)
                samples["insert_and_commit"].append(insert_ms)
                samples["save_total"].append(serialize_ms + insert_ms)

            if iteration + 1 < args.warmups + args.repeats:
                # Only remove files owned by this temporary-directory benchmark.
                for owned in Path(tmp).iterdir():
                    owned.unlink()
        print("Completed serialization and committed-write trials.", flush=True)

        # Repeated reads intentionally use a warm OS file cache. The public API
        # is also measured separately to capture the actual cache-hit path.
        with FormExpansionCache(database_path=path, form_executable="FORM-must-not-run") as cache:
            connection = cache._connection()
            for iteration in range(args.warmups + args.repeats):
                row, select_ms = timed(lambda: connection.execute(SELECT, (program,)).fetchone())
                decoded, deserialize_ms = timed(lambda: cache._decode_expansion(row[0]))
                assert decoded == terms
                del decoded
                result, hit_ms = timed(lambda: cache.get_expansion(program))
                assert result == terms
                del result
                if iteration >= args.warmups:
                    samples["select_and_fetch"].append(select_ms)
                    samples["deserialize"].append(deserialize_ms)
                    samples["load_breakdown_total"].append(select_ms + deserialize_ms)
                    samples["get_expansion_existing_connection"].append(hit_ms)
        print("Completed reads and deserialization using an open connection.", flush=True)

        def new_connection_hit():
            with FormExpansionCache(database_path=path, form_executable="FORM-must-not-run") as cache:
                return cache.get_expansion(program)

        for iteration in range(args.warmups + args.repeats):
            result, hit_ms = timed(new_connection_hit)
            assert result == terms
            del result
            if iteration >= args.warmups:
                samples["get_expansion_new_connection"].append(hit_ms)
        database_bytes = path.stat().st_size

    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "sqlite_version": sqlite3.sqlite_version,
        "source_read_only": str(args.source.resolve()),
        "temporary_database_parent": str(Path(__file__).parent),
        "repeats": args.repeats,
        "warmups": args.warmups,
        "term_count": len(terms),
        "program_bytes": len(program.encode("utf-8")),
        "json_bytes": len(payload.encode("utf-8")),
        "database_bytes": database_bytes,
        "form_order": int(re.search(r"t\(:(\d+)\)", program).group(1)),
        "program": program,
        "pragmas": pragmas,
        "notes": [
            "One existing entry; no FORM execution or parsing is timed.",
            "Each insert commits a real row in a newly initialized temporary database.",
            "Save total is serialization plus INSERT and COMMIT; initialization is separate.",
            "Read trials use warm OS file caches, with garbage collection enabled.",
            "New-connection hits include cache construction, connect, schema check, read, decode and close.",
            "Single process, no competing benchmark writers; concurrent contention is not measured.",
            "Every restored expansion is checked for exact equality outside the timed region.",
        ],
        "timings": {name: summarize(values) for name, values in samples.items()},
    }
    destination = Path(__file__).with_name("timings.json")
    destination.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({name: {key: value for key, value in values.items() if key != "samples_ms"}
                      for name, values in report["timings"].items()}, indent=2), flush=True)
    print(f"Saved {destination}", flush=True)


if __name__ == "__main__":
    main()
