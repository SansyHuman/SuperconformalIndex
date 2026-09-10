"""Math helpers."""

from functools import reduce
from math import gcd
from operator import index
from ortools.sat.python import cp_model


class _SolutionCollector(cp_model.CpSolverSolutionCallback):
    def __init__(self, variables, limit=None):
        super().__init__()
        self.variables = variables
        self.limit = limit
        self.solutions = []

    def on_solution_callback(self):
        solution = tuple(self.value(v) for v in self.variables)
        self.solutions.append(solution)

        if self.limit is not None and len(self.solutions) >= self.limit:
            self.stop_search()


def frobenius_solve(
    coefficients,
    target,
    max_solutions=None,
):
    coefficients = tuple(index(c) for c in coefficients)
    target = index(target)

    if any(c <= 0 for c in coefficients):
        raise ValueError("coefficients must be positive integers")

    if max_solutions is not None:
        max_solutions = index(max_solutions)
        if max_solutions < 0:
            raise ValueError("max_solutions must be nonnegative")
        if max_solutions == 0:
            return []

    if target < 0:
        return []

    if not coefficients:
        return [()] if target == 0 else []

    if target == 0:
        return [(0,) * len(coefficients)]

    # Reduce the size of the CP-SAT model.
    common_divisor = reduce(gcd, coefficients)

    if target % common_divisor:
        return []

    coefficients = tuple(c // common_divisor for c in coefficients)
    target //= common_divisor

    # CP-SAT uses signed 64-bit integers.
    if target > (1 << 63) - 1:
        raise OverflowError("the reduced target exceeds CP-SAT's int64 range")

    model = cp_model.CpModel()

    variables = [
        model.new_int_var(
            0,
            target // coefficient,
            f"x_{i}",
        )
        for i, coefficient in enumerate(coefficients)
    ]

    # Coefficients larger than the target have variables fixed at zero.
    active_terms = [
        coefficient * variable
        for coefficient, variable in zip(coefficients, variables)
        if coefficient <= target
    ]

    if not active_terms:
        return []

    model.add(sum(active_terms) == target)

    return _solve_frobenius_model(model, variables, max_solutions)


def frobenius_system_solve(
    coefficients,
    targets,
    max_solutions=None,
):
    """Return nonnegative integer tuples solving ``coefficients @ x = targets``.

    Each row is one equation; all rows must have the same number of columns
    and there must be one integer target per row. Coefficients must be
    nonnegative integers. Zero coefficients are allowed, but every variable
    must appear with a positive coefficient in at least one equation; an
    unconstrained variable raises ValueError rather than enumerating an
    unbounded domain. An inconsistent equation returns no solutions.

    Rows are reduced by their coefficient GCD before constructing the OR-Tools
    CP-SAT model. Remaining targets must fit its signed 64-bit integer range.
    Empty systems have zero variables and return [()]. With zero columns,
    [()] is returned exactly when all targets vanish. Solution order is not
    specified. max_solutions optionally stops after that many solutions.
    """
    rows = tuple(tuple(index(c) for c in row) for row in coefficients)
    targets = tuple(index(target) for target in targets)
    if len(rows) != len(targets):
        raise ValueError("there must be one target per coefficient row")
    width = len(rows[0]) if rows else 0
    if any(len(row) != width for row in rows):
        raise ValueError("coefficient rows must have the same length")
    if any(c < 0 for row in rows for c in row):
        raise ValueError("coefficients must be nonnegative integers")

    if max_solutions is not None:
        max_solutions = index(max_solutions)
        if max_solutions < 0:
            raise ValueError("max_solutions must be nonnegative")
        if max_solutions == 0:
            return []

    equations = []
    for row, target in zip(rows, targets):
        if target < 0:
            return []
        common_divisor = reduce(gcd, row, 0)
        if common_divisor == 0:
            if target:
                return []
            continue
        if target % common_divisor:
            return []
        equations.append((
            tuple(c // common_divisor for c in row),
            target // common_divisor,
        ))

    upper_bounds = []
    for j in range(width):
        bounds = [target // row[j] for row, target in equations if row[j]]
        if not bounds:
            raise ValueError(
                f"variable x_{j} has no positive coefficient and is unconstrained"
            )
        upper_bounds.append(min(bounds))

    # Drop fixed-zero terms before passing coefficients to CP-SAT. Their
    # coefficients can exceed int64 even when the remaining system is small.
    active_equations = []
    for row, target in equations:
        active = [(j, c) for j, c in enumerate(row) if c and upper_bounds[j]]
        if not active:
            if target:
                return []
            continue
        if target > (1 << 63) - 1:
            raise OverflowError("a reduced target exceeds CP-SAT's int64 range")
        active_equations.append((active, target))

    if not any(upper_bounds):
        return [(0,) * width]

    model = cp_model.CpModel()
    variables = [
        model.new_int_var(0, upper, f"x_{j}")
        for j, upper in enumerate(upper_bounds)
    ]
    for active, target in active_equations:
        model.add(sum(c * variables[j] for j, c in active) == target)

    return _solve_frobenius_model(model, variables, max_solutions)


def _solve_frobenius_model(model, variables, max_solutions):
    """Enumerate a bounded CP-SAT model using the shared solution collector."""
    collector = _SolutionCollector(
        variables,
        limit=max_solutions,
    )

    solver = cp_model.CpSolver()
    solver.parameters.enumerate_all_solutions = True

    # Reliable complete enumeration uses one worker.
    solver.parameters.num_workers = 1

    status = solver.solve(model, collector)

    if status == cp_model.MODEL_INVALID:
        raise ValueError(f"Invalid CP-SAT model: {solver.solution_info()}")

    if status == cp_model.UNKNOWN:
        raise RuntimeError("CP-SAT stopped before finding or rejecting solutions")

    return collector.solutions
