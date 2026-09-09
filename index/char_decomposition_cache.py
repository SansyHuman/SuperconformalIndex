"""SQLite-backed LiE cache for products of Adams-operated characters.

For an irreducible representation ``R`` and a tuple ``powers`` whose entry
``powers[j - 1]`` is ``n_j``, this module caches the decomposition

    product_j Adams(j, R) ** n_j.

Decompositions and final singlet coefficients share a local SQLite database.
Keys use Cartan types, Dynkin labels and Adams powers, independently of FORM
character names. Legacy JSON caches are imported on demand and left intact.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from concurrent.futures import ProcessPoolExecutor
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import threading
import time

from common.number_utils import as_integer, as_nonnegative_int


# Highest weight of the representation
DynkinLabels = tuple[int, ...]
# Character product number of each order of Adams operation
AdamsPowers = tuple[int, ...]
# Character decomposition of key representation and value coefficient
Decomposition = dict[DynkinLabels, int]
# Decomposition request of (cartan type, highest weight, Adams powers)
DecompositionRequest = tuple[str, DynkinLabels, AdamsPowers]
# Products of characters with dynkin labels and Adams powers
CharacterProduct = tuple[tuple[DynkinLabels, AdamsPowers], ...]


DEFAULT_CACHE_DATABASE = Path(__file__).resolve().parents[1] / "char_decomposition_cache.db"
_SCHEMA_VERSION = 1
_CARTAN_TYPE_RE = re.compile(r"(?:[ABCD]\d+|E[678]|F4|G2)\Z")
_LIE_NOTICE_PREFIX = "New tree space with maximum number of nodes:"
_LIE_TERM_RE = re.compile(r"([+-]?\d+)X\[([0-9,]*)\]")
_PROCESS_CACHE = None


def _canonical_cartan_type(value: str) -> str:
    """Normalize the algebra name."""
    if not isinstance(value, str):
        raise ValueError("Cartan type must be a string")
    result = re.sub(r"[\s_-]+", "", value).upper()
    if _CARTAN_TYPE_RE.fullmatch(result) is None:
        raise ValueError(f"invalid LiE Cartan type {value!r}")
    return result


def _canonical_labels(labels: Iterable[int]) -> DynkinLabels:
    """Convert the input into a nonempty tuple of nonnegative integers."""
    try:
        result = tuple(as_nonnegative_int(value, "Dynkin label") for value in labels)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Dynkin labels must be nonnegative integers") from exc
    if not result or any(value < 0 for value in result):
        raise ValueError("Dynkin labels must be a nonempty tuple of nonnegative integers")
    return result


def _canonical_adams_powers(powers: Iterable[int]) -> AdamsPowers:
    """Produce a unique representation of Adams powers."""
    try:
        raw = tuple(as_nonnegative_int(value, "Adams power") for value in powers)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Adams powers must be nonnegative integers") from exc
    if any(value < 0 for value in raw):
        raise ValueError("Adams powers must be nonnegative integers")

    order = sum(position * value for position, value in enumerate(raw, start=1))
    if order <= 0:
        raise ValueError("at least one Adams power must be positive")
    if any(raw[position - 1] for position in range(order + 1, len(raw) + 1)):
        raise ValueError("an Adams index cannot exceed the total Adams order")
    return raw[:order] + (0,) * max(0, order - len(raw))


def _adams_order(powers: AdamsPowers) -> int:
    """Calculate the total Adams order."""
    return sum(position * value for position, value in enumerate(powers, start=1))


def _decomposition_dependencies(
    powers: AdamsPowers,
) -> tuple[AdamsPowers, ...]:
    """Return the two lower-factor products used by the recursive calculation."""
    if sum(powers) <= 1:
        return ()
    split_position = next(
        position
        for position, value in enumerate(powers, start=1)
        if value
    )
    left_raw = list(powers)
    left_raw[split_position - 1] -= 1
    left = _canonical_adams_powers(left_raw)
    right_raw = [0] * split_position
    right_raw[-1] = 1
    return left, tuple(right_raw)


def _json_key(value) -> str:
    """Serialize a normalized key into compact JSON text."""
    return json.dumps(value, separators=(",", ":"))


def _canonical_request(
    cartan_type: str, labels: Iterable[int], powers: Iterable[int],
) -> DecompositionRequest:
    """Normalize the Cartan type, labels, and Adams powers."""
    algebra = _canonical_cartan_type(cartan_type)
    labels = _canonical_labels(labels)
    if len(labels) != int(algebra[1:]):
        raise ValueError("Dynkin-label length does not match Cartan rank")
    return algebra, labels, _canonical_adams_powers(powers)


def _canonical_product(algebra, product) -> CharacterProduct:
    """Merge repeated representations by adding their power vectors and sort factors."""
    merged = {}
    for labels, powers in product:
        _, labels, powers = _canonical_request(algebra, labels, powers)
        previous = merged.setdefault(labels, [])
        previous.extend([0] * max(0, len(powers) - len(previous)))
        for position, value in enumerate(powers):
            previous[position] += value
    return tuple(sorted(
        ((labels, _canonical_adams_powers(powers)) for labels, powers in merged.items()),
        reverse=True,
    ))


def _initialize_decomposition_worker(
    database_path: str,
    lie_executable: str,
    max_nodes: int,
    max_objects: int,
    timeout: float,
) -> None:
    global _PROCESS_CACHE
    _PROCESS_CACHE = CharacterDecompositionCache(
        database_path=database_path, lie_executable=lie_executable,
        max_nodes=max_nodes, max_objects=max_objects, timeout=timeout, max_workers=1,
    )


def _generate_decomposition_in_worker(request: DecompositionRequest) -> Decomposition:
    if _PROCESS_CACHE is None:
        raise RuntimeError("character-decomposition worker was not initialized")
    # Dependencies were committed by the parent after the preceding level.
    # Return the new value to the parent, which batches writes for this level.
    return _PROCESS_CACHE._calculate_decomposition(*request)


def _format_labels(labels: DynkinLabels) -> str:
    """Convert Dynkin labels to LiE syntax."""
    return "[" + ",".join(str(value) for value in labels) + "]"


def format_lie_decomposition(decomposition: Decomposition) -> str:
    """Convert a structured decomposition to a LiE polynomial."""
    if not decomposition:
        raise ValueError("the zero virtual representation has no LiE polynomial here")
    terms = []
    for labels, coefficient in sorted(decomposition.items()):
        if coefficient:
            terms.append(f"{coefficient:+d}X{_format_labels(labels)}")
    return "".join(terms).lstrip("+")


def parse_lie_decomposition(text: str, rank: int) -> Decomposition:
    """Parse one LiE decomposition polynomial into structured terms."""
    compact = "".join(text.split())
    while any(pair in compact for pair in ("++", "+-", "-+", "--")):
        compact = (
            compact.replace("++", "+")
            .replace("+-", "-")
            .replace("-+", "-")
            .replace("--", "+")
        )
    if compact == "0":
        return {}

    matches = list(_LIE_TERM_RE.finditer(compact))
    if not matches:
        raise RuntimeError(f"could not parse LiE decomposition: {text!r}")
    reconstructed = "".join(match.group(0) for match in matches)
    if reconstructed.lstrip("+") != compact.lstrip("+"):
        raise RuntimeError(f"partially parsed LiE decomposition: {text!r}")

    result: Decomposition = {}
    for match in matches:
        coefficient = int(match.group(1))
        labels = tuple(int(value) for value in match.group(2).split(","))
        if len(labels) != rank:
            raise RuntimeError(
                f"LiE returned {len(labels)} labels for a rank-{rank} algebra"
            )
        updated = result.get(labels, 0) + coefficient
        if updated:
            result[labels] = updated
        else:
            result.pop(labels, None)
    return result


class CharacterDecompositionCache:
    """Persist exact character decompositions and singlet coefficients in SQLite.

    With no path arguments, use ``char_decomposition_cache.db`` at the project
    root. The positional ``cache_directory`` remains supported and places that
    filename inside the supplied directory. ``database_path`` selects a file
    explicitly; these two arguments are mutually exclusive.

    Each thread opens its own connection and keeps its own in-memory cache.
    Workers open connections after process creation. SQLite transactions cover
    only completed cache writes, never LiE calculations. Coefficients are stored
    as decimal strings to preserve arbitrary-size signed integers.
    """

    def __init__(
        self,
        cache_directory: str | Path | None = None,
        *,
        database_path: str | Path | None = None,
        lie_executable: str = "lie",
        max_nodes: int = 9_999_999,
        max_objects: int = 9_999_999,
        timeout: float = 600,
        max_workers: int | None = None,
    ) -> None:
        if cache_directory is not None and database_path is not None:
            raise ValueError("supply either cache_directory or database_path")
        if database_path is not None:
            path = Path(database_path)
        elif cache_directory is not None:
            path = Path(cache_directory) / DEFAULT_CACHE_DATABASE.name
        else:
            path = DEFAULT_CACHE_DATABASE
        self.database_path = path.resolve()
        self.cache_directory = self.database_path.parent
        self.lie_executable = lie_executable
        self.max_nodes = int(max_nodes)
        self.max_objects = int(max_objects)
        self.timeout = timeout
        if max_workers is not None and int(max_workers) <= 0:
            raise ValueError("max_workers must be positive or None")
        self.max_workers = None if max_workers is None else int(max_workers)
        self._local = threading.local()
        self._legacy_directories = [self.cache_directory]
        if self.database_path == DEFAULT_CACHE_DATABASE.resolve():
            self._legacy_directories.extend([
                self.cache_directory / "char_decomposition_cache",
                self.cache_directory / "index" / "char_decomposition_cache_data",
            ])

    def _state(self):
        """Maintain each thread's connection, memory caches and pending writes."""
        state = getattr(self._local, "state", None)
        if state is None or state["pid"] != os.getpid():
            # Never use a connection inherited from a parent process.
            if state is not None and state["connection"] is not None:
                state["connection"].close()
            state = dict(pid=os.getpid(), connection=None, decompositions={},
                         singlets={}, imported=set(), pending=None)
            self._local.state = state
        return state

    @staticmethod
    def _retry_busy(operation):
        for attempt in range(3):
            try:
                return operation()
            except sqlite3.OperationalError as exc:
                code = getattr(exc, "sqlite_errorcode", 0) & 0xff
                if code not in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED) or attempt == 2:
                    raise
                time.sleep(0.05 * (attempt + 1))

    def _connection(self) -> sqlite3.Connection:
        """Open SQLite lazily and enable WAL."""
        state = self._state()
        if state["connection"] is not None:
            return state["connection"]
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path, timeout=30)
        try:
            mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
            if mode != "wal":
                self._retry_busy(lambda: connection.execute("PRAGMA journal_mode=WAL").fetchone())
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, _SCHEMA_VERSION):
                raise RuntimeError(f"unsupported character-cache schema version {version}")
            if version == 0:
                def initialize():
                    with connection:
                        connection.execute("BEGIN IMMEDIATE")
                        connection.execute("""
                            CREATE TABLE IF NOT EXISTS character_decompositions (
                                algebra TEXT NOT NULL,
                                dynkin_labels TEXT NOT NULL,
                                adams_powers TEXT NOT NULL,
                                adams_order INTEGER NOT NULL,
                                terms_json TEXT NOT NULL,
                                PRIMARY KEY (algebra, dynkin_labels, adams_powers)
                            ) WITHOUT ROWID
                        """)
                        connection.execute("""
                            CREATE TABLE IF NOT EXISTS singlet_coefficients (
                                algebra TEXT NOT NULL,
                                product_key TEXT NOT NULL,
                                coefficient TEXT NOT NULL,
                                PRIMARY KEY (algebra, product_key)
                            ) WITHOUT ROWID
                        """)
                        connection.execute(f"PRAGMA user_version={_SCHEMA_VERSION}")
                self._retry_busy(initialize)
        except BaseException:
            connection.close()
            raise
        state["connection"] = connection
        return connection

    def close(self) -> None:
        """Close this thread's connection and release its in-memory entries."""
        state = self._state()
        if state["connection"] is not None:
            state["connection"].close()
        self._local.state = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()

    def cache_path(self, cartan_type, labels, adams_order) -> Path:
        """Return the shared SQLite file (legacy path-helper signature)."""
        _canonical_request(cartan_type, labels, (1,))
        if as_nonnegative_int(adams_order, "Adams order") == 0:
            raise ValueError("Adams order must be positive")
        return self.database_path

    @staticmethod
    def _encode_decomposition(decomposition):
        """Convert decomposition dictionary to JSON text."""
        return _json_key([
            [labels, str(as_integer(coefficient, "coefficient"))]
            for labels, coefficient in sorted(decomposition.items()) if coefficient
        ])

    @staticmethod
    def _decode_decomposition(payload):
        """Convert JSON text to decomposition dictionary."""
        return {tuple(labels): int(coefficient) for labels, coefficient in json.loads(payload)}

    def _write_decompositions(self, entries):
        """Write decompositions to database."""
        rows = [
            (algebra, _json_key(labels), _json_key(powers), _adams_order(powers),
             self._encode_decomposition(decomposition))
            for (algebra, labels, powers), decomposition in entries
        ]
        if not rows:
            return
        connection = self._connection()
        def write():
            with connection:
                connection.executemany("""
                    INSERT INTO character_decompositions VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT (algebra, dynkin_labels, adams_powers) DO NOTHING
                """, rows)
        self._retry_busy(write)

    def _import_legacy(self, request):
        algebra, labels, powers = request
        order = _adams_order(powers)
        filename = f"{algebra}_dynkin_{'-'.join(map(str, labels))}_adams_order_{order}.json"
        imported = self._state()["imported"]
        for directory in self._legacy_directories:
            path = directory / algebra / filename
            if path in imported or not path.is_file():
                continue
            with path.open(encoding="utf-8") as handle:
                payload = json.load(handle)
            if (payload.get("schema_version") != 1 or payload.get("algebra") != algebra
                    or tuple(payload.get("dynkin_labels", ())) != labels
                    or payload.get("adams_order") != order):
                raise RuntimeError(f"cache metadata does not match filename: {path}")
            entries = []
            for entry in payload.get("decompositions", []):
                key = _canonical_request(algebra, labels, entry["adams_powers"])
                if _adams_order(key[2]) != order:
                    raise RuntimeError(f"cache Adams order does not match filename: {path}")
                decomposition = {}
                for term in entry["terms"]:
                    term_labels = _canonical_labels(term["dynkin_labels"])
                    if len(term_labels) != len(labels):
                        raise RuntimeError(f"cache term rank does not match filename: {path}")
                    coefficient = as_integer(term["coefficient"], "coefficient")
                    if coefficient:
                        decomposition[term_labels] = coefficient
                entries.append((key, decomposition))
            self._write_decompositions(entries)
            imported.add(path)

    def _lookup_decomposition(self, request):
        """Retrieve cached decomposition result."""
        memory = self._state()["decompositions"]
        if request in memory:
            return memory[request]
        algebra, labels, powers = request
        parameters = (algebra, _json_key(labels), _json_key(powers))
        sql = """SELECT terms_json FROM character_decompositions
                 WHERE algebra=? AND dynkin_labels=? AND adams_powers=?"""
        connection = self._connection()
        row = connection.execute(sql, parameters).fetchone()
        if row is None:
            self._import_legacy(request)
            row = connection.execute(sql, parameters).fetchone()
        if row is None:
            return None
        decomposition = self._decode_decomposition(row[0])
        memory[request] = decomposition
        return decomposition

    def get_decomposition(
        self, cartan_type: str, labels: Iterable[int], powers: Iterable[int],
    ) -> Decomposition:
        """Return a copy of a persisted decomposition, calculating it on a miss."""
        request = _canonical_request(cartan_type, labels, powers)
        result = self._lookup_decomposition(request)
        if result is None:
            result = self._calculate_decomposition(*request)
            pending = self._state()["pending"]
            if pending is None:
                self._write_decompositions([(request, result)])
            else:
                pending.append((request, result))
                if len(pending) >= 64:
                    self._write_decompositions(pending)
                    pending.clear()
            self._state()["decompositions"][request] = result
        return dict(result)

    @contextmanager
    def _batch_decompositions(self):
        """Buffer completed results without holding a transaction during LiE."""
        state = self._state()
        if state["pending"] is not None:
            yield
            return
        state["pending"] = []
        try:
            yield
        finally:
            pending = state["pending"]
            state["pending"] = None
            self._write_decompositions(pending)

    def get_decompositions(
        self, requests: Sequence[tuple[str, Iterable[int], Iterable[int]]],
    ) -> list[Decomposition]:
        """Generate missing prerequisites by level, reusing persisted results."""
        requests = [_canonical_request(*request) for request in requests]
        required = set()
        pending = list(set(requests))
        by_level = {}
        while pending:
            request = pending.pop()
            if request in required:
                continue
            required.add(request)
            if self._lookup_decomposition(request) is not None:
                continue
            algebra, labels, powers = request
            by_level.setdefault(sum(powers), []).append(request)
            pending.extend((algebra, labels, dependency)
                           for dependency in _decomposition_dependencies(powers))
        if by_level:
            workers = min(self.max_workers or (os.cpu_count() or 1),
                          max(map(len, by_level.values())))
            if workers == 1:
                with self._batch_decompositions():
                    for level in sorted(by_level):
                        for request in sorted(by_level[level]):
                            self.get_decomposition(*request)
            else:
                # Do not fork this client's live SQLite connection.
                self.close()
                with ProcessPoolExecutor(
                    max_workers=workers, initializer=_initialize_decomposition_worker,
                    initargs=(str(self.database_path), self.lie_executable,
                              self.max_nodes, self.max_objects, self.timeout),
                ) as executor:
                    for level in sorted(by_level):
                        level_requests = sorted(by_level[level])
                        results = executor.map(_generate_decomposition_in_worker, level_requests)
                        entries = list(zip(level_requests, results, strict=True))
                        self._write_decompositions(entries)
                        self._state()["decompositions"].update(entries)
        return [self.get_decomposition(*request) for request in requests]

    def _lookup_singlets(self, algebra, keys):
        """Retrieve cached singlet coefficients."""
        memory = self._state()["singlets"]
        connection = self._connection()
        result = {}
        for key in dict.fromkeys(keys):
            if (algebra, key) in memory:
                result[key] = memory[algebra, key]
                continue
            row = connection.execute(
                "SELECT coefficient FROM singlet_coefficients WHERE algebra=? AND product_key=?",
                (algebra, key),
            ).fetchone()
            if row is not None:
                result[key] = memory[algebra, key] = int(row[0])
        return result

    def _write_singlets(self, algebra, entries):
        """Insert singlet coefficients into database."""
        if not entries:
            return
        connection = self._connection()
        def write():
            with connection:
                connection.executemany("""
                    INSERT INTO singlet_coefficients VALUES (?, ?, ?)
                    ON CONFLICT (algebra, product_key) DO NOTHING
                """, [(algebra, key, str(value)) for key, value in entries.items()])
        self._retry_busy(write)
        self._state()["singlets"].update(((algebra, key), value) for key, value in entries.items())

    def get_singlet_multiplicities(
        self,
        cartan_type: str,
        rank: int,
        products: Sequence[Sequence[tuple[Iterable[int], Iterable[int]]]],
    ) -> list[int]:
        """Look up character-product singlets before loading any decomposition.

        Each product contains ``(Dynkin labels, Adams powers)`` pairs for one
        simple factor. Repeated irreps are merged and factors sorted; conjugate
        irreps retain their actual orientation. Cached zeros are valid hits.
        """
        algebra = _canonical_cartan_type(cartan_type)
        if as_nonnegative_int(rank, "rank") != int(algebra[1:]):
            raise ValueError("rank does not match Cartan type")
        products = [_canonical_product(algebra, product) for product in products]
        keys = [_json_key(["characters", product]) for product in products]
        found = self._lookup_singlets(algebra, keys)
        missing = {key: product for key, product in zip(keys, products) if key not in found}
        if missing:
            requests = sorted({(algebra, labels, powers)
                               for product in missing.values() for labels, powers in product})
            decompositions = dict(zip(requests, self.get_decompositions(requests), strict=True))
            expanded = [[decompositions[algebra, labels, powers] for labels, powers in product]
                        for product in missing.values()]
            values = self._compute_singlet_multiplicities(algebra, rank, expanded)
            entries = dict(zip(missing, values, strict=True))
            self._write_singlets(algebra, entries)
            found.update(entries)
        return [found[key] for key in keys]

    def singlet_multiplicities(
        self,
        cartan_type: str,
        rank: int,
        products: Sequence[Sequence[Decomposition]],
    ) -> list[int]:
        """Cache singlets for callers supplying already decomposed characters."""
        algebra = _canonical_cartan_type(cartan_type)
        if as_nonnegative_int(rank, "rank") != int(algebra[1:]):
            raise ValueError("rank does not match Cartan type")
        products = [list(product) for product in products]
        keys = [_json_key(["decompositions", sorted(
            self._encode_decomposition(decomposition) for decomposition in product
        )]) for product in products]
        found = self._lookup_singlets(algebra, keys)
        missing = {key: product for key, product in zip(keys, products) if key not in found}
        if missing:
            values = self._compute_singlet_multiplicities(algebra, rank, list(missing.values()))
            entries = dict(zip(missing, values, strict=True))
            self._write_singlets(algebra, entries)
            found.update(entries)
        return [found[key] for key in keys]

    def _compute_singlet_multiplicities(
        self,
        cartan_type: str,
        rank: int,
        products: Sequence[Sequence[Decomposition]],
    ) -> list[int]:
        """Return trivial-irrep coefficients for several tensor products.

        Each item in ``products`` is a sequence of already decomposed virtual
        representations.  All nontrivial queries are submitted to one LiE process.
        """
        algebra = _canonical_cartan_type(cartan_type)
        zero = (0,) * int(rank)
        results: list[int | None] = [None] * len(products)
        expressions: list[str] = []
        expression_positions: list[int] = []

        for position, product in enumerate(products):
            if any(not decomposition for decomposition in product):
                results[position] = 0
            elif not product:
                results[position] = 1
            elif len(product) == 1:
                results[position] = product[0].get(zero, 0)
            else:
                expressions.append(self._singlet_expression(algebra, zero, product))
                expression_positions.append(position)

        if expressions:
            output = self._run_lie(expressions)
            if len(output) != len(expressions):
                raise RuntimeError(
                    f"LiE returned {len(output)} singlet results for "
                    f"{len(expressions)} queries"
                )
            for position, value in zip(expression_positions, output, strict=True):
                try:
                    results[position] = int(value)
                except ValueError as exc:
                    raise RuntimeError(
                        f"LiE returned a nonintegral singlet multiplicity: {value!r}"
                    ) from exc

        if any(value is None for value in results):
            raise RuntimeError("internal error while collecting LiE singlet results")
        return [int(value) for value in results]

    def _calculate_decomposition(
        self,
        algebra: str,
        labels: DynkinLabels,
        powers: AdamsPowers,
    ) -> Decomposition:
        """Calculate decomposition of given Adams powers."""
        level = sum(powers)
        if level == 1:
            adams = next(
                position
                for position, value in enumerate(powers, start=1)
                if value
            )
            expression = f"Adams({adams},{_format_labels(labels)},{algebra})"
        else:
            left, right = _decomposition_dependencies(powers)
            left_decomposition = self.get_decomposition(algebra, labels, left)
            right_decomposition = self.get_decomposition(algebra, labels, right)
            expression = (
                f"tensor({format_lie_decomposition(left_decomposition)},"
                f"{format_lie_decomposition(right_decomposition)},{algebra})"
            )

        output = self._run_lie([expression])
        if not output:
            raise RuntimeError(f"LiE returned no result for {expression!r}")
        return parse_lie_decomposition("".join(output), len(labels))

    def _singlet_expression(
        self,
        algebra: str,
        zero: DynkinLabels,
        product: Sequence[Decomposition],
    ) -> str:
        """Construct a LiE tensor expression for coefficient of singlet."""
        polynomials = [format_lie_decomposition(item) for item in product]
        if len(polynomials) == 2:
            return (
                f"tensor({polynomials[0]},{polynomials[1]},"
                f"{_format_labels(zero)},{algebra})"
            )

        intermediate = f"tensor({polynomials[0]},{polynomials[1]},{algebra})"
        for polynomial in polynomials[2:-1]:
            intermediate = f"tensor({intermediate},{polynomial},{algebra})"
        return (
            f"tensor({intermediate},{polynomials[-1]},"
            f"{_format_labels(zero)},{algebra})"
        )

    def _run_lie(self, expressions: Sequence[str]) -> list[str]:
        """Execute LiE on given expressions."""
        result = self._execute_lie(expressions, configure_memory=False)
        lines = self._lie_output_lines(result.stdout)
        needs_retry = (
            result.returncode != 0
            or bool(result.stderr.strip())
            or any("(" in line or "error" in line.lower() for line in lines)
        )
        if needs_retry:
            result = self._execute_lie(expressions, configure_memory=True)
            lines = self._lie_output_lines(result.stdout)

        if result.returncode != 0 or result.stderr.strip():
            raise RuntimeError(
                f"LiE failed with code {result.returncode}: "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )
        return lines

    def _execute_lie(
        self,
        expressions: Sequence[str],
        *,
        configure_memory: bool,
    ) -> subprocess.CompletedProcess[str]:
        """Send LiE program through standard input and capture output."""
        commands = list(expressions)
        if configure_memory:
            commands[:0] = [
                f"maxnodes {self.max_nodes}",
                f"maxobjects {self.max_objects}",
            ]
        code = "\n".join(commands)
        try:
            return subprocess.run(
                [self.lie_executable],
                input=code,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"LiE executable {self.lie_executable!r} was not found"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("LiE calculation timed out") from exc

    @staticmethod
    def _lie_output_lines(stdout: str) -> list[str]:
        """Remove empty lines and LiE's informational messages."""
        return [
            line.strip()
            for line in stdout.splitlines()
            if line.strip() and not line.startswith(_LIE_NOTICE_PREFIX)
        ]
