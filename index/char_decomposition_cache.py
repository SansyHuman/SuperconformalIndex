"""File-backed LiE cache for products of Adams-operated characters.

For an irreducible representation ``R`` and a tuple ``powers`` whose entry
``powers[j - 1]`` is ``n_j``, this module caches the decomposition

    product_j Adams(j, R) ** n_j.

Cache filenames use the project's canonical Lie-algebra convention and Dynkin
labels, for example ``A2_dynkin_1-0_adams_order_4.json``.  Cache contents are
structured JSON and never depend on field names such as ``q`` or ``phi``.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from concurrent.futures import ProcessPoolExecutor
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


# Highest weight of the representation
DynkinLabels = tuple[int, ...]
# Character product number of each order of Adams operation
AdamsPowers = tuple[int, ...]
# Character decomposition of key representation and value coefficient
Decomposition = dict[DynkinLabels, int]
# Decomposition request of (cartan type, highest weight, Adams powers)
DecompositionRequest = tuple[str, DynkinLabels, AdamsPowers]


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
        result = tuple(int(value) for value in labels)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Dynkin labels must be nonnegative integers") from exc
    if not result or any(value < 0 for value in result):
        raise ValueError("Dynkin labels must be a nonempty tuple of nonnegative integers")
    return result


def _canonical_adams_powers(powers: Iterable[int]) -> AdamsPowers:
    """Produce a unique representation of Adams powers."""
    try:
        raw = tuple(int(value) for value in powers)
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


@contextmanager
def _exclusive_cache_directory(directory: Path):
    """Serialize cache-file merges between Linux worker processes."""
    directory.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _initialize_decomposition_worker(
    cache_directory: str,
    lie_executable: str,
    max_nodes: int,
    max_objects: int,
    timeout: float,
) -> None:
    """Create one process-local cache client for a process-pool worker."""
    global _PROCESS_CACHE
    _PROCESS_CACHE = CharacterDecompositionCache(
        cache_directory,
        lie_executable=lie_executable,
        max_nodes=max_nodes,
        max_objects=max_objects,
        timeout=timeout,
        max_workers=1,
    )


def _generate_decomposition_in_worker(
    request: DecompositionRequest,
) -> Decomposition:
    """Generate one requested decomposition in an initialized worker."""
    if _PROCESS_CACHE is None:
        raise RuntimeError("character-decomposition worker was not initialized")
    _PROCESS_CACHE._memory.clear()
    return _PROCESS_CACHE.get_decomposition(*request)


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
    """Generate, persist and reuse LiE character decompositions."""

    def __init__(
        self,
        cache_directory: str | Path | None = None,
        *,
        lie_executable: str = "lie",
        max_nodes: int = 9_999_999,
        max_objects: int = 9_999_999,
        timeout: float = 600,
        max_workers: int | None = None,
    ) -> None:
        self.cache_directory = (
            Path(cache_directory)
            if cache_directory is not None
            else Path(__file__).with_name("char_decomposition_cache_data")
        )
        self.lie_executable = lie_executable
        self.max_nodes = int(max_nodes)
        self.max_objects = int(max_objects)
        self.timeout = timeout
        if max_workers is not None and int(max_workers) <= 0:
            raise ValueError("max_workers must be positive or None")
        self.max_workers = None if max_workers is None else int(max_workers)
        self._memory: dict[Path, dict[AdamsPowers, Decomposition]] = {}

    def cache_path(
        self,
        cartan_type: str,
        labels: Iterable[int],
        adams_order: int,
    ) -> Path:
        """Return the canonical cache path for one algebra, irrep and order."""
        algebra = _canonical_cartan_type(cartan_type)
        canonical_labels = _canonical_labels(labels)
        order = int(adams_order)
        if order <= 0:
            raise ValueError("Adams order must be positive")
        label_text = "-".join(str(value) for value in canonical_labels)
        filename = f"{algebra}_dynkin_{label_text}_adams_order_{order}.json"
        return self.cache_directory / algebra / filename

    def get_decomposition(
        self,
        cartan_type: str,
        labels: Iterable[int],
        powers: Iterable[int],
    ) -> Decomposition:
        """Return the cached decomposition, generating it with LiE if absent."""
        algebra = _canonical_cartan_type(cartan_type)
        canonical_labels = _canonical_labels(labels)
        canonical_powers = _canonical_adams_powers(powers)
        order = _adams_order(canonical_powers)
        path = self.cache_path(algebra, canonical_labels, order)
        entries = self._load_cache(path, algebra, canonical_labels, order)
        if canonical_powers in entries:
            return dict(entries[canonical_powers])

        decomposition = self._calculate_decomposition(
            algebra, canonical_labels, canonical_powers
        )

        with _exclusive_cache_directory(path.parent):
            latest = self._load_cache(
                path, algebra, canonical_labels, order, force_reload=True
            )
            if canonical_powers not in latest:
                latest[canonical_powers] = decomposition
                self._write_cache(path, algebra, canonical_labels, order, latest)
        self._memory[path] = latest
        return dict(latest[canonical_powers])

    def get_decompositions(
        self,
        requests: Sequence[tuple[str, Iterable[int], Iterable[int]]],
    ) -> list[Decomposition]:
        """Return several decompositions, generating cold entries in processes.

        Recursive prerequisites are generated in increasing factor-count order.
        Requests at the same level are independent and therefore run concurrently.
        Warm entries are read directly without creating a process pool.
        """
        canonical_requests = [
            (
                _canonical_cartan_type(cartan_type),
                _canonical_labels(labels),
                _canonical_adams_powers(powers),
            )
            for cartan_type, labels, powers in requests
        ]
        if not canonical_requests:
            return []

        required = set(canonical_requests)
        pending = list(canonical_requests)
        while pending:
            algebra, labels, powers = pending.pop()
            for dependency in _decomposition_dependencies(powers):
                request = (algebra, labels, dependency)
                if request not in required:
                    required.add(request)
                    pending.append(request)

        by_level: dict[int, list[DecompositionRequest]] = {}
        for request in required:
            algebra, labels, powers = request
            path = self.cache_path(algebra, labels, _adams_order(powers))
            entries = self._load_cache(path, algebra, labels, _adams_order(powers))
            if powers not in entries:
                by_level.setdefault(sum(powers), []).append(request)

        if by_level:
            max_requests = max(len(level_requests) for level_requests in by_level.values())
            configured_workers = self.max_workers or (os.cpu_count() or 1)
            worker_count = min(configured_workers, max_requests)

            if worker_count == 1:
                for level in sorted(by_level):
                    for request in sorted(by_level[level]):
                        self.get_decomposition(*request)
            else:
                with ProcessPoolExecutor(
                    max_workers=worker_count,
                    initializer=_initialize_decomposition_worker,
                    initargs=(
                        str(self.cache_directory.resolve()),
                        self.lie_executable,
                        self.max_nodes,
                        self.max_objects,
                        self.timeout,
                    ),
                ) as executor:
                    for level in sorted(by_level):
                        level_requests = sorted(by_level[level])
                        list(executor.map(_generate_decomposition_in_worker, level_requests))

        for algebra, labels, powers in required:
            path = self.cache_path(algebra, labels, _adams_order(powers))
            self._memory.pop(path, None)
        return [self.get_decomposition(*request) for request in canonical_requests]

    def singlet_multiplicities(
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

    def _load_cache(
        self,
        path: Path,
        algebra: str,
        labels: DynkinLabels,
        order: int,
        *,
        force_reload: bool = False,
    ) -> dict[AdamsPowers, Decomposition]:
        """Load json decomposition data."""
        if not force_reload and path in self._memory:
            return self._memory[path]
        if not path.exists():
            result: dict[AdamsPowers, Decomposition] = {}
            self._memory[path] = result
            return result

        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if (
            payload.get("schema_version") != _SCHEMA_VERSION
            or payload.get("algebra") != algebra
            or tuple(payload.get("dynkin_labels", ())) != labels
            or payload.get("adams_order") != order
        ):
            raise RuntimeError(f"cache metadata does not match filename: {path}")

        result = {}
        for entry in payload.get("decompositions", []):
            powers = tuple(int(value) for value in entry["adams_powers"])
            decomposition = {
                tuple(int(value) for value in term["dynkin_labels"]): int(
                    term["coefficient"]
                )
                for term in entry["terms"]
                if int(term["coefficient"])
            }
            result[powers] = decomposition
        self._memory[path] = result
        return result

    def _write_cache(
        self,
        path: Path,
        algebra: str,
        labels: DynkinLabels,
        order: int,
        entries: dict[AdamsPowers, Decomposition],
    ) -> None:
        """Serialize decomposition as json and atomically write to file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": _SCHEMA_VERSION,
            "algebra": algebra,
            "dynkin_labels": list(labels),
            "adams_order": order,
            "decompositions": [
                {
                    "adams_powers": list(powers),
                    "terms": [
                        {
                            "coefficient": coefficient,
                            "dynkin_labels": list(term_labels),
                        }
                        for term_labels, coefficient in sorted(decomposition.items())
                        if coefficient
                    ],
                }
                for powers, decomposition in sorted(entries.items())
            ],
        }

        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=path.parent,
                prefix=path.name + ".",
                suffix=".tmp",
                delete=False,
            ) as handle:
                json.dump(payload, handle, indent=2, sort_keys=False)
                handle.write("\n")
                temporary_name = handle.name
            os.replace(temporary_name, path)
        finally:
            if temporary_name is not None:
                temporary_path = Path(temporary_name)
                if temporary_path.exists():
                    temporary_path.unlink()
