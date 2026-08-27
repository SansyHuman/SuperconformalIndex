import sys
from wolframclient.evaluation import WolframLanguageSession


from functools import reduce
from math import gcd
from operator import index
from sympy.liealgebras import root_system
import sympy

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


def frobenius_solve_ortools(
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


# 스크립트를 실행하려면 여백의 녹색 버튼을 누릅니다.
if __name__ == '__main__':
    print(sys.version)

    c = root_system.RootSystem("A2")
    print(c.all_roots())
    print(c.root_space())

    wolfram_kenel_path = "/usr/local/Wolfram/Wolfram/15.0/Executables/WolframKernel"

    mcode = rf"""
iVector[t_, y_, v_] = (t^2*v - t^4/v - t^3*(y + y^-1) + 2*t^6)/((1 - t^3*y) (1 - t^3 y^-1));
iHHyper[t_, y_, v_] = (t^2/v^(1/2) - t^4*v^(1/2))/((1 - t^3*y) (1 - t^3 y^-1));
chiFund[z_] = z + z^-1;
chiAdj[z_] = z^2 + 1 + z^-2;
iSum[t_, y_, v_, z_] = iVector[t, y, v]*chiAdj[z] + 8*iHHyper[t, y, v]*chiFund[z];
PE[f_, t_, y_, v_, z_, cutoff1_, cutoff2_] := 
 Exp[Series[
   Sum[PowerExpand[1/n*f[t^n, y^n, v^n, z^n]], {{n, 1, cutoff1}}], {{t, 
    0, cutoff2}}]];
Harr[z_] = (1 - z^2) (1 - z^-2);
integrand = Harr[z]*PE[iSum, t, y, v, z, 18, 18];
intExp = ExpandAll[Normal[integrand]];
index = Expand[SeriesCoefficient[intExp, {{z, 0, 0}}]/2];
indexRefined = (index - 1) /. {{v -> 1}};
{{ToString[InputForm[index]], ToString[InputForm[indexRefined]]}}
"""

    solutions = frobenius_solve_ortools([2, 5, 6, 8, 10, 18, 22, 35], 35)
    print(sorted(solutions))

    wolfram_session = WolframLanguageSession(wolfram_kenel_path)
    index, indexRefined = wolfram_session.evaluate(mcode)
    print(f"Index: {index}")
    print(f"Refined index: {indexRefined}")

    wolfram_session.terminate()
