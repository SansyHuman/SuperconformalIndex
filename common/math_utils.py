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
