# SuperconformalIndex Project Handoff

Last updated: **2026-09-10 (Asia/Seoul)**.

## Where this session stopped

Simple- and product-group irrep and conformal matter enumeration are implemented.
The new `enumerate_product_theory_candidates` accepts an iterable of Cartan
strings and solves the coupled beta equations with `frobenius_system_solve`. Reality classification uses Tits' formula; all
146 comparisons with Sage's Frobenius-Schur indicator matched across 23 Cartan
types. A32 enumeration returns six candidates in about 1.1 seconds after
algebra initialization.

The user then supplied Claude's independent correctness audit. A read-only
review reproduced its main findings, including the full/half-hyper database
normalization gap and a missing factor of two in this handoff's beta-function
formula. The handoff formula was corrected first. Earlier fixes standardize
conjugate canonicalization on the lexicographically larger labels throughout
enumeration, flavor metadata, and database hashing; correct the Coulomb-module
docstring; and correct the reference PDF's central-charge payload table. The
latest database fix pairs pseudoreal half hypers into full hypers for hashing,
so equivalent full, half, and mixed descriptions deduplicate. Shared flavor
data now stores half-hyper units without the submitted full/half split; raw
realization records retain it. Schema version 6 removes the two redundant
flavor-factor columns. After adding product theory enumeration, the SQLite character cache and sparse
singlet projection, the full suite runs 170 tests: 168 passed and two live-MySQL
tests were skipped. Existing realization hashes are not rehashed
automatically; rows written with the previous full/half convention need a
separate migration before relying on deduplication against new imports.

The Coulomb-branch index, plethystic-log spectrum extraction, property
integration, and schema version 6 are also implemented. **No HL/Higgs-branch
calculator or flavor-refined index has been implemented.** The earlier HL/Higgs
discussion is retained below as context, not an accepted implementation task.

The latest cleanup removes legacy JSON-cache import/discovery and the obsolete
`cache_path()` wrapper. Use `cache.database_path` to locate the SQLite file.
The latest optimization splits each character monomial into two parts before
requesting decompositions, then obtains the singlet by pairing dual irreps.
A temporary implementation matched the existing SQLite code and independent
weight calculations before promotion. A8 SQCD through t^18 now takes 2.44 seconds
for the full cold index, versus 6.21 seconds before; warm time stays about 1.70
seconds. The unlimited A32 SQCD run through t^18 completed in 94.293 seconds
cold and 1.786 seconds warm. The intermediate `psi_3(adjoint)^2` decomposition
alone took 82.699 seconds (87.7% of the cold total); this is the main remaining
bottleneck. Both revised PDFs now document the cache and projection algorithm,
and both have retained LaTeX sources. Unrevised PDF content was preserved.

The user prefers exact arithmetic, FORM for symbolic expansions, reuse of
existing helpers, and gauge information supplied through `GaugeFactorData`.
Their standing conjugacy preference is to choose the fundamental over its
antifundamental: use the lexicographically larger Dynkin labels whenever
identifying conjugates, including simultaneous conjugation for product groups.
Treat this document as session context; future work depends on the user's
next request.

## Project location and status

Project root:

```text
/home/subo-lee/PycharmProjects/SuperconformalIndex
```

The project studies four-dimensional N=2 Lagrangian superconformal field
theories. It currently provides anomaly and conformality checks, common theory
properties, superconformal/Coulomb-index calculation, Coulomb-generator
dimensions, bounded irrep enumeration, simple- and product-group conformal matter
enumeration, and MySQL persistence.

HEAD is on `master` at commit `0a402ec`. The Frobenius-system solver, product
theory enumerator, SQLite character cache, legacy-cache cleanup and sparse
singlet projection are committed. Current changes update both index PDFs,
preserve their LaTeX/build inputs and refresh this handoff. The unlimited A32
profile is retained under `output/benchmarks/a32_unlimited/`. No commit,
staging change, or remote fetch was performed for this update.
Other untracked entries include:

```text
PROJECT_HANDOFF.md
anomalies/__pycache__/
common/__pycache__/
index/__pycache__/
test/__pycache__/
```

LiE cache locations are described below. Generated caches and bytecode should
not be mistaken for source changes.

## Runtime dependencies

The active implementation requires:

- SageMath; the code was developed with SageMath 10.7.
- FORM, available as the `form` executable.
- LiE, available as the `lie` executable.
- PyMySQL and a MySQL server for database operations.
- OR-Tools (`ortools`) for `common/math_utils.py` and the theory enumerator.
  `cp_model` is imported at module scope, so importing `common/n2_theory_iter`
  requires OR-Tools even before calling the solver. It is not required by the
  standalone anomaly/index APIs. The configured Sage environment has OR-Tools
  9.15.6755.

Run Python entry points and tests with Sage's Python environment, for example:

```bash
sage -python -m unittest discover -s test -p 'test_*.py' -v
```

The working command in this local environment was:

```bash
DOT_SAGE=/tmp/codex-sage-cache \
  /home/subo-lee/miniconda3/envs/sage/bin/sage -python \
  -m unittest discover -s test -p 'test_*.py' -v
```

FORM and LiE are available as `/usr/bin/form` and `/usr/bin/lie`. The `/tmp`
Sage directory is runtime scratch space and may need to be recreated later.

## Shared utilities

- `common/form_utils.py`: `run_form`, `split_top_level`, and
  `split_signed_terms`. FORM executes in an isolated temporary directory with
  timeout and error handling. The full-index and Coulomb modules reuse these.
- `common/number_utils.py`: exact integer and rational validation.
  `as_integer` and `as_nonnegative_int` reject Python floats, including `1.0`,
  and booleans. Rational dimension inputs should use `Fraction`, Sage `QQ`,
  integers, or accepted rational strings, rather than floats.
- `common/json_utils.py`: exact `Fraction` serialization as
  `{"numerator": n, "denominator": d}`; tuples serialize as JSON arrays.
- `common/math_utils.py`: `frobenius_solve(coefficients, target,
  max_solutions=None)` enumerates nonnegative integer solutions of one linear
  equation with positive integer coefficients. It reduces by the coefficient
  gcd, bounds each variable by `target // coefficient`, and uses OR-Tools
  CP-SAT with one worker and an all-solutions callback. Rational equations
  must first be scaled to integers. `max_solutions` permits a partial result;
  CP-SAT integer limits apply. The low-level integer conversion uses
  `operator.index`, which also accepts booleans, unlike `number_utils`.
- `frobenius_system_solve(coefficients, targets, max_solutions=None)` in the
  same module solves a rectangular system with nonnegative integer
  coefficients. Zero coefficients are allowed; each variable must have a
  positive coefficient somewhere to give a finite bound. It reduces each row
  by its GCD and bounds each variable by the minimum target/coefficient over
  the rows in which it appears. Empty systems have zero variables and return
  `[()]`; inconsistent systems return `[]`. Coefficients of fixed-zero
  variables are omitted from the CP-SAT model, including oversized integers.
  Both solvers share `_solve_frobenius_model` and `_SolutionCollector`.

## Common JSON input format

A simple gauge group is represented by:

```json
{
  "algebra": "A1",
  "hypermultiplets": [
    {
      "representation": "fundamental",
      "number": 4,
      "kind": "full"
    }
  ]
}
```

A product gauge group is represented by:

```json
{
  "gauge_groups": [
    {"id": "left", "algebra": "A1"},
    {"id": "right", "algebra": "A1"}
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
```

Conventions:

- Dynkin labels use Bourbaki numbering.
- Supported simple algebras are `A_r`, `B_r`, `C_r`, `D_r`, `E6`, `E7`,
  `E8`, `F4`, and `G2`.
- Gauge factors are assumed to be simply connected.
- Type `C_n` uses the group notation `Sp(n)`, not `USp(2n)`.
- The default hypermultiplet kind is `full`.
- Half hypermultiplets are accepted only in pseudoreal representations.
- Omitted factors in a product representation are treated as singlets.
- Representations can be given by supported names or explicit Dynkin labels.

Example input files are in `anomalies/`.

## Lie-algebra backend

File: `anomalies/lie_algebra.py`

This module uses SageMath for:

- Cartan and root-system data.
- Lie-algebra dimensions and dual Coxeter numbers.
- Representation dimensions.
- Quadratic Casimirs and Dynkin indices.
- Conjugate representations.
- Exact coroot data for reality classification by Tits' formula.
- Named-representation Dynkin labels.

`SimpleLieAlgebra` stores the Sage objects and derived invariants for one
simple algebra. Expensive algebra and representation calculations are cached.

`representation_reality` first compares the validated labels with their
conjugate; a non-self-dual irrep is `"complex"`. For a self-dual highest weight:

```text
FS(lambda) = (-1)^<lambda, 2 rho^vee>,
2 rho^vee = sum_(positive roots alpha) 2 alpha / <alpha,alpha>.
```

`_tits_parities` caches `<omega_i, 2 rho^vee> mod 2` for each algebra. A dot
product with the Dynkin labels then gives `"real"` for even parity and
`"pseudoreal"` for odd parity. All arithmetic is exact, including for unequal
root lengths; no symmetric/exterior squares are computed. The formula is
Theorem 3.6 of https://arxiv.org/abs/0704.0165.

The index normalization is `T(adjoint) = C2(adjoint) = h_dual` and
`T(SU(N) fundamental) = 1/2`. For type A, `quadratic_casimir` relies on
`character.highest_weight()` to project the ambient weight to the traceless
subspace. Replacing this with a raw sum of ambient fundamental weights would
be incorrect: the SU(5) fundamental would give `T = 15/16` instead of `1/2`.
The same common-coordinate shift does not affect the coroot pairings in
Tits' formula.

The accepted low-rank conventions avoid redundant simple-algebra names: use
`A1` for `B1` or `C1`, `A3` for `D3`, and a product of `A1` factors for `D2`.
Both `B2` and `C2` remain accepted even though they are isomorphic.

## Anomaly and conformality checker

File: `anomalies/check_n2_anomalies.py`

The checker handles simple and product gauge groups. It checks:

- Input shape and representation validity.
- Whether every half hypermultiplet is pseudoreal.
- Perturbative gauge anomalies.
- The conventional mod-two Witten anomaly for `A1`, `C_n`, and the
  isomorphic `B2` case.
- The one-loop beta function of every gauge factor.
- Spectator-dimension factors for product representations.

For gauge factor G_i, the one-loop coefficient is

```text
b_0,i = 2 h_i^vee
        - sum_H n_H (2 epsilon_H) T_i(R_H,i)
          product_(j != i) dim(R_H,j),
```

where `epsilon_H` is 1 for a full hypermultiplet and 1/2 for a half
hypermultiplet. Thus a full hyper contributes `2T` and a half hyper contributes
`T`, including spectator dimensions. For SU(N) with `N_f` full fundamentals,
this gives `b_0 = 2N - N_f`. The previous handoff omitted the factor of two;
the implementation already used the correct formula.

With `I_i(R) = T_i(R_i) * product_(j != i) dim(R_j)`, the conventional Witten
parity is `sum_(half H) n_H * 2 I_i(R_H) mod 2`. Half-hyper multiplicities
need not be even separately; the weighted total determines the anomaly.
For valid matter, `b_0,i = 0` implies this parity vanishes: doubling the beta
equation leaves an even vector/full-hyper contribution. This implication
applies to the conventional anomaly on spin manifolds checked here. The
parity test remains useful for nonconformal inputs. See also section 2 of
https://arxiv.org/abs/1309.5160.

The checker does not require pure flavor 't Hooft anomalies to vanish. It also
does not check global anomalies that depend on a non-simply-connected quotient
of the gauge group.

CLI example:

```bash
sage -python anomalies/check_n2_anomalies.py anomalies/example_e6.json
```

## Representation and theory enumeration

File: `common/n2_theory_iter.py`

```python
enumerate_irreps(gauge_factor, *, max_index=None, inclusive=True,
                 include_singlet=False, identify_conjugates=True)
enumerate_product_irreps(gauge_factors, *, max_indices=None, inclusive=True,
                         include_singlet=False, identify_conjugates=True)
enumerate_simple_theory_candidates(gauge_group)
enumerate_product_theory_candidates(gauge_groups)
```

The irrep APIs accept `GaugeFactorData` objects. The simple API returns sorted
`(DynkinLabels, Fraction)` pairs. The product API returns
`(labels_by_factor_id, indices_by_factor_id)` pairs; its indices already include
all spectator dimensions. `max_indices` overrides bounds by factor ID.

Every automatic bound is **`2 * dual_coxeter_number`**, inclusive by default.
This safely includes irreps usable as half hypers before their reality is
known. Full hypers must subsequently obey the stronger cost constraint
`2T <= 2h_dual`. `inclusive=False` makes the selected bound strict.

The simple search increments Dynkin labels and prunes branches above the
index bound. The product search also prunes using partial spectator indices.
Individual factor singlets are always allowed in product representations;
`include_singlet` controls only the representation trivial under the entire
gauge group. The global singlet is excluded by default.

`identify_conjugates=True` retains the lexicographically **larger** label
tuple, favoring lower-numbered Dynkin nodes, such as the SU(N) fundamental.
Conjugacy filters the output, not the search branches. For product groups it
identifies only simultaneous conjugation of every factor; independently
discarding factor conjugates would lose representations such as `(3, 3bar)`.
The property and database canonicalizers use the same larger-tuple convention.
Explicit conjugation and the full-hyper index calculation still retain the
actual conjugate representation where mathematically required.

`enumerate_simple_theory_candidates("A2")` accepts a Cartan-type string and
returns input-schema dictionaries with `algebra` and `hypermultiplets`.
Pseudoreal irreps are counted in half-hyper units; real and complex irreps
are counted as full hypers. It scales exact rational costs by an LCM and calls
`frobenius_solve` to solve

```text
sum_R multiplicity_R * cost_R = 2 h_dual,
cost_R = T(R) for pseudoreal R, otherwise 2 T(R).
```

Terms with zero multiplicity are omitted. Irreps whose cost exceeds the budget
have multiplicity zero. The function enumerates conformal matter candidates
without explicitly invoking the anomaly checker; it omits free singlet matter.
It returns only the half-hyper description for pseudoreal matter, avoiding a
duplicate full/half description within its output. The database independently
identifies equivalent descriptions by pairing half hypers into full hypers,
with at most one remaining half hyper per pseudoreal gauge representation.

Verified candidate counts are A1: 2, A2: 3, G2: 2, C3: 8, and A32: 6.
A1 gives eight half fundamentals or one full adjoint. A32 (SU(33)) reduces to
`n_fund + 31*n_antisym + 35*n_sym + 66*n_adj = 66`.
Measured A32 times were about 5.48 seconds including initial algebra setup
and 1.12 seconds with the algebra cached. These are local measurements, not
performance guarantees. Before the Tits change, the first reality check alone
exceeded a 40-second profiling cutoff.

`enumerate_product_theory_candidates(["A1", "C2"])` accepts any nonempty
iterable of Cartan strings, including a one-shot iterator. A bare string is
rejected. Factors receive IDs `gauge_1`, `gauge_2`, ... in input order, and
Cartan names are normalized with `get_lie_algebra`. Repeated types and single
factors are supported. The output uses the product input schema with
`gauge_groups` and `hypermultiplets`; representation values are lists, so the
checker accepts the dictionaries directly without a JSON round trip.

It reuses `enumerate_product_irreps`, caches factor reality by Cartan type and
Dynkin labels, and determines whole-product reality. Each irrep contributes
`T_a(R)` per half hyper if pseudoreal, otherwise `2*T_a(R)` per full hyper.
Irreps exceeding any factor's budget are dropped. The remaining exact rational
beta equations are scaled to integers independently by row and solved with
`frobenius_system_solve`. Odd half-hyper counts are retained. There is no anomaly
check in the enumerator itself; free gauge singlets and zero counts are omitted.
Both coupled and decoupled theories are included, and factor permutations are
not identified. SU(2) x SU(2) has exactly eight candidates for labelled factors.
Tests compare mixed-group results to exhaustive rational enumeration and
single-factor results to the existing simple enumerator.

## Theory properties

File: `common/n2_theory_properties.py`

`calculate_n2_theory_properties(data)` returns a dictionary containing:

```python
{
    "group": ...,
    "lagrangian_scft_candidate": ...,
    "flavor_symmetry": ...,
    "conformal_manifold_dimension": ...,
    "exactly_marginal_gauge_couplings": ...,
    "central_charges": ...,
    "coulomb_branch_index": ...,
    "coulomb_branch_spectrum": ...,
    "superconformal_index": ...,
}
```

The key is singular: `superconformal_index`. Both index values are serialized
strings for SCFT candidates. `coulomb_branch_spectrum` is a sorted tuple of
`Fraction` dimensions, with repetitions preserved. Central charges, both
indices, and the spectrum are `None` for non-SCFT candidates.

### Flavor symmetry

Hypermultiplets are grouped by their complete irreducible gauge
representation. For `n` identical full hypers, the connected flavor group is:

- `U(n)` for a complex gauge representation.
- `Sp(n)` for a real gauge representation.
- `SO(m)` for a pseudoreal gauge representation, where `m` counts half-hyper
  units and one full hyper contributes two units.

The complex representation and its conjugate are assigned to the same flavor
block. For a product gauge group, reality is the reality of the external tensor
product of all factor representations.

### Conformal manifold

For a Lagrangian SCFT candidate, the current implementation counts one exactly
marginal gauge coupling for each simple gauge factor:

```text
dim_C M_conf = number of simple gauge factors.
```

For a nonconformal input, this dimension is `None`.

### Central charges

Let `n_v` be the total dimension of the gauge algebra and `n_h` the effective
hypermultiplet dimension. The implementation uses exact fractions:

```text
a = (5 n_v + n_h) / 24,
c = (2 n_v + n_h) / 12.
```

The returned `central_charges` payload contains only `a` and `c`; the effective
counts `n_v` and `n_h` are internal calculations, not returned properties.

### Index integration

The property calculator computes the superconformal index through `t^18` by
calling `calculate_index_internal`. This internal API accepts already parsed
gauge factors and hypermultiplets, so the index code does not repeat anomaly
validation.

The property-calculation cache is intentionally stored at the project root:

```text
/home/subo-lee/PycharmProjects/SuperconformalIndex/char_decomposition_cache.db
```

The property calculator computes the Coulomb-branch index through scaling
dimension 90 by passing the parsed gauge factors to
`calculate_lagrangian_coulomb_branch_index`.

The user's `_calculate_coulomb_branch_spectrum(anomaly_result)` obtains Weyl
invariant degrees from the same gauge factors and converts them to `Fraction`.
It is now called by `calculate_n2_theory_properties`. Public convenience APIs
include `calculate_central_charges`, `calculate_superconformal_index`,
`calculate_coulomb_branch_index`, and `calculate_coulomb_branch_spectrum`.

## Superconformal-index implementation

Files:

- `index/n2_theory_index.py`
- `index/char_decomposition_cache.py`

The original Mathematica and pure-Sage implementations were removed. The
current implementation supports both simple and product gauge groups and uses:

- FORM to expand and collect the truncated representation-valued plethystic
  exponential.
- LiE to perform Adams operations and intermediate tensor-product decompositions.
- Exact sparse pairing of dual irreps to extract the final gauge singlet.
- A process pool to generate independent cold-cache decompositions in
  parallel.

For product gauge groups, FORM maintains separate formal characters for each
factor, and singlet projection is performed factor by factor.

Flavor fugacities are effectively set to 1: matter copies enter as integer
multiplicities in `_matter_character_multiplicities`. This preserves total
counts but omits flavor representation information. The separate flavor-group
metadata in the property calculator does not make the index flavor-refined.

### Character decomposition cache

`CharacterDecompositionCache` stores decompositions and final singlet coefficients
in SQLite using Python's `sqlite3`. Both standalone index calls and property
calculations default to `char_decomposition_cache.db` at the project root.
The generated database and its journal sidecars are ignored by git.

`character_decompositions` has a composite primary key of Cartan type, input
Dynkin labels and canonical Adams powers, plus weighted Adams order and a JSON
payload of output labels and signed decimal-string coefficients.
`singlet_coefficients` keys the Cartan type and canonical product description,
storing a signed decimal-string integer. SQLite `user_version=1` records the
cache schema/convention version, independently of the theory MySQL schema.

`get_singlet_multiplicities(cartan_type, rank, products)` accepts each product
as a sequence of `(labels, Adams powers)` pairs and looks up the scalar before
requesting any decompositions. Repeated labels merge; factors sort in descending
order; actual conjugate orientations remain distinct. The existing
`singlet_multiplicities` API for decomposed virtual characters also persists
results, using a distinct key namespace. Zero and negative results are valid.

Connections and memory caches are local to each thread. Process workers open
their own connections; the process-pool parent batches completed writes by
dependency level. Sequential generation flushes at 64 completed entries and at
batch completion. WAL and short transactions with bounded busy retries support
concurrent clients. LiE never runs inside a write transaction. Context-manager
use closes connections explicitly. The full-decomposition API remains available;
singlet requests now use the optimized projection described below.

Existing `cache_directory=` arguments still work, selecting the directory for
the default database filename. New `database_path=` selects a file, and the CLI
adds `--cache-database`. These options are mutually exclusive. Cache lookup
uses memory and SQLite only; missing entries use LiE decompositions and exact
singlet pairing as needed. Legacy
JSON import, directory discovery and the `cache_path()` compatibility wrapper
have been removed. Existing SQLite entries remain valid with no schema change.
Old JSON files are no longer consulted; the cleanup does not delete them.

The candidate was implemented under `/tmp/sci-sqlite-cache/candidate`, compared
against the original, and promoted only after exact agreement and measured
speedups. For A8 SQCD through t^18, three-trial median complete-index times were
8.71 to 6.17 seconds cold and 4.19 to 1.71 seconds warm. Some short cold runs
incur 30–50 ms of setup overhead. All 2,343 persisted decomposition comparisons
and all seven benchmark index cases matched. Details and raw timings are in
`output/benchmarks/sqlite_cache_benchmark.md` and `sqlite_cache_timings.json`;
`test/benchmark_character_cache.py` reproduces comparisons with baseline git
revision `d4d103a`. After removing the obsolete legacy-import test, the full suite runs 163 tests,
with two live-MySQL skips.

### Singlet projection without decomposing the complete product

For virtual characters `A = sum a_lambda chi_lambda` and
`B = sum b_mu chi_mu`, the invariant coefficient of `A*B` is
`sum_lambda a_lambda b_(lambda dual)`. Coefficients may be negative. Pseudoreal
irreps pair with themselves without an extra Frobenius-Schur sign.

- `_split_character_product` expands multiplicities into individual Adams
  factors and greedily balances two sides using `j * sum(labels)` as an
  approximate cost. It splits across repeated irreps before their entire
  products are decomposed. Individual Adams operations remain intact.
- `_character_singlets` plans required partial products, uses the existing
  persistent cache/process pool for products of one base irrep, and memoizes
  mixed partial decompositions in thread-local memory.
- `_singlet_pair` contracts the two partial decomposition dictionaries by
  looking up dual labels. `_dual_permutation` caches the Dynkin-diagram
  permutation obtained from the existing Sage duality helper.
- `_tensor_decompositions` is used only for intermediate mixed products.
  The complete product is never tensor-decomposed by the singlet path.
  Already-decomposed callers also use partial products and the same final
  pairing. Full decomposition calls still work when explicitly requested.

SQLite schema version 1 and product keys are unchanged. All 4,996 old singlet
entries from the benchmark databases were reused without recalculation.
The prototype in `/tmp/sci-singlet-projection/candidate` matched 319 singlet
queries against the existing algorithm; 202 also matched independent SU(2) and
SU(3) weight calculations. All 216 dual-label comparisons against Sage matched
across 18 Cartan types, covering every supported family. Seven benchmark index
cases matched exactly, including product groups and half hypers. Three-trial
cold projection medians were A8 t^18: 4.60 -> 0.849 seconds; A16 t^12:
1.47 -> 0.207 seconds; A32 t^8: 0.469 -> 0.117 seconds. The full A8 t^18 index
improved 6.21 -> 2.44 seconds; warm performance stayed about 1.70 seconds.

Details are in `output/benchmarks/singlet_projection_benchmark.md` and
`singlet_projection_timings.json`. The reusable benchmark accepts
`--baseline-ref a9b7009 --baseline-label existing --candidate-label sparse`.
After promotion, the complete suite ran 170 tests in 11.461 seconds, with 168
passed and two live-MySQL skips. The seven new tests in
`test/test_singlet_projection.py` cover signed complex/pseudoreal pairings,
large integers, grouped Adams splitting, mixed products, independent SU(2)/SU(3)
weights, serial/parallel generation, trivial characters and zeros.

The split is a heuristic and does not eliminate all intermediate decomposition
costs. A16 t^18 projection finished in 1.92 seconds while the previous code
exceeded 25 seconds; no full old/new comparison was possible for that case.
The earlier A32 t^18 probe exceeded its 25-second limit; the unlimited follow-up
on 10 September completed. It used SU(33) SQCD with 66 full fundamental hypers,
`processes=1`, `timeout=None`, and a fresh temporary SQLite file. Complete times
were 94.293 seconds cold and 1.786 seconds warm, with 117 exactly matching
Laurent monomials. Input validation/algebra initialization took 4.483 seconds,
FORM 1.357 seconds, FORM parsing 0.212 seconds, and projection 88.229 seconds.
One LiE request for `psi_3(adjoint)^2` took 82.699 seconds: 10 irrep terms in each
input and 91 in its output. All other LiE calls together took 5.066 seconds.
The warm run made no LiE calls. These are single wall-clock measurements with
one worker, not medians or default-process-count timings. See
`output/benchmarks/a32_unlimited/report.md`, `summary.json`, `events.jsonl` and
`results.json`; the exact index and profiling script are retained there too.
No production code was changed for profiling.

### Sage result ring and serialization

`_to_sage_polynomial` returns one flat Laurent polynomial in

```text
QQ[t^+-1, y^+-1, u^+-1].
```

The ring formally permits negative powers of `t`, but calculated indices only
contain nonnegative `t` powers. Because the ring is flat, converting an index
to `str` gives a sum of monomials without grouping coefficients with common
`t` powers, for example:

```text
t^4*u^4 + 36*t^4*u^-2 - t^5*y*u^2
```

The public function `parse_index_polynomial(text)` converts this stored string
back into the canonical Sage Laurent-polynomial ring. It preserves exact
rational coefficients and validates the allowed polynomial grammar before
using Sage evaluation.

Main APIs:

```python
calculate_index(data, order, ...)
calculate_index_internal(factors, hypermultiplets, order, ...)
calculate_index_from_file(path, order, ...)
parse_index_polynomial(text)
```

CLI example:

```bash
sage -python index/n2_theory_index.py \
  anomalies/example_a1.json \
  --order 18 \
  --cache-database char_decomposition_cache.db
```

## Coulomb-branch implementation

Files:

- `index/n2_theory_coulomb_branches.py`
- `test/test_n2_theory_coulomb_branches.py`

These replaced `index/n2_theory_branches.py` and its corresponding test file.
Use the new import path. The spectrum extraction function is
`extract_coulomb_branch_spectrum_from_index`, and the module's introductory
docstring now uses that current callable name.

Public APIs (all in the Coulomb module):

```python
calculate_coulomb_branch_index(spectrum=None, max_dimension=None,
                              *, full_index=None, ...)
calculate_coulomb_branch_index_from_full_index(full_index,
                                             *, max_dimension=None)
calculate_lagrangian_coulomb_branch_index(gauge_factors, max_dimension, ...)
coulomb_branch_spectrum_from_gauge_factors(gauge_factors)
calculate_plethystic_exponential(plethystic_log, max_dimension, ...)
calculate_plethystic_logarithm(coulomb_branch_index, max_dimension, ...)
extract_coulomb_branch_spectrum_from_index(coulomb_branch_index,
                                         max_dimension, ...)
parse_coulomb_branch_index(text)
```

`gauge_factors` accepts a `GaugeFactorData` or an iterable of them. Lagrangian
generator dimensions are the degrees of the basic Weyl-invariant polynomials,
obtained using `WeylGroup(cartan_type).degrees()`. Their sorted multiset includes
repetitions within a factor (e.g. `D4`: 2, 4, 4, 6) and across product factors.
The direct gauge-spectrum API returns integers; the property helper returns
`Fraction` objects. Matter is unnecessary for this Coulomb calculation.

For generator dimensions Delta_i:

```text
I_C(x) = PE[sum_i x^Delta_i] = product_i (1 - x^Delta_i)^(-1).
```

Spectrum input may be an iterable or dimension-to-multiplicity mapping.
The lower-level PE accepts signed integer coefficients for future
generator/relation data. FORM performs the truncated expansion and rational
arithmetic. Rational dimensions are rescaled with an LCM, using
`q = x^(1/L)` so `x^Delta = q^(L*Delta)`. Results are converted to
`COULOMB_INDEX_RING = PuiseuxSeriesRing(QQ, "x")`.

The full-index Coulomb limit in project conventions holds `x = t^2*u^2`
fixed. A monomial `t^a*y^b*u^c` survives if `a == c` and maps to `x^(c/2)`.
The code rejects divergent terms (`a < c`), surviving `y` dependence, and
negative dimensions. Both a Sage full-index polynomial and its string are
accepted.

The inverse calculation uses

```text
PL[I](x) = sum_(k>=1) mu(k)/k * log I(x^k).
```

FORM evaluates the ordinary logarithm by expanding `log(1 + delta)`, where
`delta = I - 1`. Python applies the exact Mobius coefficient transform:

```text
log I(q) = sum_n b_n q^n
[q^m] PL[I](q) = sum_(k divides m) mu(k)/k * b_(m/k).
```

The existing FORM runner, output parser, and conversion to the Sage ring are
reused. `calculate_plethystic_logarithm` returns signed rational coefficients.
`extract_coulomb_branch_spectrum_from_index` requires nonnegative integral PL
coefficients and returns repeated `Fraction` dimensions; negative coefficients
or nonintegral multiplicities raise `ValueError`.

Input requires constant coefficient 1 and no negative powers. A finite-precision
Sage series must be known through the requested inclusive cutoff. Series strings
emitted by the project are supported, including fractional exponents. Generated
truncations are polynomial-like outputs without an `O(...)` precision marker:
callers must retain the original cutoff and must not request coefficients beyond
it. A nonnegative PL through a finite cutoff does not establish global freeness.

For example, the truncation of `PE[x^2]` through degree two is `1 + x^2` and
reports infinite precision as a Sage object. Incorrectly requesting its PL
through degree four produces `x^2 - x^4`; that negative term is an artifact of
exceeding the known cutoff, not a relation in the original Coulomb ring.

Verified examples from the session:

- `PE[x^2 + x^3]` through dimension 8 gives PL `x^2 + x^3` and spectrum `(2, 3)`.
- Dimension `6/5` survives the PE/PL round trip, including serialized input.
- Repeated dimensions retain their multiplicity.
- `PE[2*x^2 - x^4]` returns signed PL `2*x^2 - x^4`; the free-spectrum API rejects it.

## MySQL database

File: `common/n2_theory_db.py`

The database uses the default PyMySQL client. The current schema version is 6.
The tables are:

- `schema_metadata`
- `theories`
- `theory_properties`
- `lagrangian_realizations`
- `non_lagrangian_realizations`
- `gauge_factors`
- `hypermultiplets`
- `hypermultiplet_representations`
- `flavor_symmetry_factors`
- `exactly_marginal_couplings`

The `non_lagrangian_realizations` table is currently a placeholder for future
work.

Central charges are stored exactly as numerator/denominator JSON. Stored,
indexed generated decimal columns permit efficient numerical range queries.
The full index is stored as a JSON string in `superconformal_index_json`, the
Coulomb index as a JSON string in `coulomb_branch_index_json`, and the spectrum
as an array of exact fractions in `coulomb_branch_spectrum_json`. All three also
appear under their corresponding keys in the combined `properties_json`.

Schema migration 1 to 2 added decimal central-charge columns. Migration 2 to 3
renamed `superconformal_indices` and `superconformal_indices_json` to their
singular forms.

Migration 3 to 4 renamed the former Coulomb placeholder/index column
`coulomb_branch_spectrum_json` to `coulomb_branch_index_json` and moved its JSON
key. Migration 4 to 5 adds a new nullable `coulomb_branch_spectrum_json` column
for actual generator dimensions, keeping the index separate. Migration 4 to 5
does not compute spectra for existing rows.

Migration 5 to 6 drops `full_hypermultiplets` and `half_hypermultiplets` from
the theory-level `flavor_symmetry_factors` table, retaining `half_hyper_units`.
The original split remains in the realization's `hypermultiplets` rows and
input/anomaly JSON. This schema migration does not rehash or merge existing
realizations, or eagerly rewrite their shared JSON.

`_insert_shared_properties` backfills the spectrum column and combined JSON if
the existing JSON matches the new properties except for the missing spectrum
key or the obsolete full/half flavor split. It removes the split before
comparison and rewrites matching legacy JSON to the current shape. It still
rejects physical property mismatches, including different half-hyper units.

**Backfill limitation:** `store_lagrangian_theory` returns early for an already
stored realization, before calling `_insert_shared_properties`. Simply
reimporting the identical realization therefore does not trigger this backfill.
The earlier conversational statement that every repeated store backfills older
rows was too broad. A dedicated backfill or a change to the duplicate path would
be future work; neither was implemented during this handoff update.

### Duplicate behavior

`store_lagrangian_theory` is storage-idempotent for the same normalized
Lagrangian realization:

- It returns the existing theory and realization IDs.
- `StoredTheory.inserted` is `False`.
- The duplicate return path does not insert or update theory/realization data;
  schema initialization still occurs before this lookup.
- A newly supplied display name is ignored.
- The existing `updated_at` value is not changed.

The canonical realization payload ignores hypermultiplet order, combines
duplicate hypermultiplets, omits zero multiplicities, and identifies a complex
representation with its conjugate. Product gauge-factor order is still
significant.

Canonicalization now selects the larger label tuple, favoring fundamental
representations, consistently with enumeration and flavor metadata. This
changes hashes and shared flavor labels for complex representations compared
with the previous smaller-tuple convention. Existing database rows have not
been migrated; their old hashes/properties need a deliberate migration before
relying on deduplication across the convention change.

**Full/half normalization is fixed for new imports:** for each pseudoreal
representation, hashing first sums `2 * full + half`, then uses full pairs and
one remaining half if needed. Product groups use the reality of the complete
tensor-product representation. Real and complex representations remain full
hypers. SU(2) with four full fundamentals, eight half fundamentals, or a mixed
description now has one hash and returns the same theory/realization IDs.
Tests cover both insertion orders and attaching with an explicit `theory_id`.
For C3, odd half-hyper multiplicities in distinct irreps remain separate.

`_shared_properties` removes `full_hypermultiplets` and `half_hypermultiplets`
from a copy of flavor metadata. The public property calculator still reports
the original split. Equivalent shared properties compare equal, including
legacy JSON that retains the split. Actual FORM/LiE calculations confirm equal
superconformal indices through `t^6` and Coulomb indices through order 12 for
full/half SU(2) fundamentals and SU(2)^3 trifundamentals. Database behavior and
schema migration were tested with recording/mocked connections; no live
database was modified.

The new full/half normalization preserves hashes for descriptions already
written entirely as full hypers under the current conjugacy convention.
Previously stored unpaired half-hyper hashes and duplicate theory rows still
need a separate data migration. Shared flavor metadata additionally contains
gauge representations and factor IDs, which must be considered when supporting
different realizations of one theory.

Anomaly checking and property calculation, including the index, currently
happen before the duplicate lookup. Consequently, importing an existing
realization still incurs those calculations. The database path also performs
anomaly parsing twice: once in `_checked_results` and again in
`calculate_n2_theory_properties`.

Different dual Lagrangian descriptions are not recognized automatically. Use
`theory_id` or `--theory-id` to attach a different realization to an existing
theory. Its shared properties must match the existing `properties_json`
exactly, apart from the missing-spectrum backfill case described above;
otherwise the insertion is rolled back.

New data insertion uses one explicit InnoDB transaction. A failure rolls back
the theory-related DML, although schema initialization and migration occur
before that transaction.

CLI example:

```bash
export N2_DB_PASSWORD='...'

sage -python common/n2_theory_db.py \
  anomalies/example_e6.json \
  database_name \
  --user database_user \
  --name "E6 theory"
```

## Tests

Test files:

- `test/test_check_n2_anomalies.py`
- `test/test_n2_theory_properties.py`
- `test/test_n2_theory_index.py`
- `test/test_n2_theory_coulomb_branches.py`
- `test/test_n2_theory_db.py`
- `test/test_n2_theory_iter.py`
- `test/test_lie_algebra.py`
- `test/test_math_utils.py`

Run all tests with:

```bash
sage -python -m unittest discover -s test -p 'test_*.py' -v
```

The latest full-suite run, on 2026-09-09 after adding product theory enumeration, used the
actual Sage, FORM, and LiE backends and reported:

```text
Ran 150 tests in 9.733s
OK (skipped=2)
```

That means **148 passed and 2 skipped**. The two skipped tests require live
MySQL; schema migration and inserts were covered by recording/mock tests, not
a live database run. The exact invocation disabled live database tests:

```bash
N2_TEST_MYSQL_DATABASE= DOT_SAGE=/tmp/codex-sage-cache \
  /home/subo-lee/miniconda3/envs/sage/bin/sage -python -B \
  -m unittest discover -s test -p 'test_*.py' -v
```

The 96-test result in the previous handoff and reference PDF was an older,
dated snapshot. Claude's 116-test snapshot predates the four Tits/A32 tests.
The read-only audit review ran 120 tests; four subsequent canonicalization
regressions brought the count to 124. Ten full/half database regressions brought
the count to 134, including one test using actual FORM/LiE index calculations.
Nine Frobenius-system tests and seven product-theory tests brought the count
up to 150. These include exhaustive comparisons for 60 seeded small integer
systems and mixed products A1 x A2, A1 x C2, and C2 x G2, plus SU(2)^3 odd
trifundamental counts and SU(3)^2 conjugate orientations.

Coverage includes irrep bounds and conjugates, product spectator factors,
simple-theory enumeration against an exhaustive rational reference, and all
six expected A32 contents. The direct Tits/Sage comparison covers 146 irreps
across 23 Cartan types, including every supported family, singlets, adjoints,
and real/complex/pseudoreal examples. All comparisons matched. Existing tests
also cover Coulomb PE/PL, fractional dimensions, precision validation, property
serialization, schema version 6, full/half deduplication, and the shared-property
backfill helper.
Canonicalization tests cover simple A/D/E complex conjugate pairs and product
bifundamentals, verifying that simultaneous conjugates share hashes and flavor
labels while `(3, 3)` and `(3, 3bar)` remain distinct.

The property and database unit tests mock the expensive index calculation.
Index tests use temporary cache directories and delete them afterward. Thus,
the test suite does not normally populate the project-root cache.

Live MySQL tests require environment variables such as:

```bash
export N2_TEST_MYSQL_DATABASE='some_test_database'
export N2_TEST_MYSQL_USER='...'
export N2_TEST_MYSQL_PASSWORD='...'
```

The test database name must contain `test`.

## Documentation

- `anomalies/README.md`
- `index/n2_theory_index_Mathematical_Background.pdf`
- `output/pdf/n2_implementation_reference_summary.pdf`
- `output/pdf/n2_implementation_reference_summary.tex`
- `output/pdf/n2_theory_index_Mathematical_Background.tex`
- `output/pdf/source_assets/n2_background_preserved_pages_2_to_4.pdf`
- `output/pdf/BUILD.md`

The PDF files contain the mathematical background, implementation equations,
references, and explanations of the FORM and LiE code.

The implementation reference PDF and its LaTeX source correctly state that
`central_charges` contains exact `a,c` only. The 2026-09-09 database update
expands sections 4.4-4.6 to cover schema version 6: all ten tables, nine foreign-key
relationships, primary/unique keys, shared versus realization ownership,
full/half normalization, and migration/backfill limitations. It also records the
134-test validation result as a dated historical snapshot.

The 10 September update revises section 3.3 of the implementation reference and
sections 6-11 plus relevant architecture/API wording of the index-background
PDF. They explain Schur orthogonality, `Hom_G(V*,W)`, dual highest weights,
signed/pseudoreal pairings, the splitter and helper functions, the SQLite
schema and concurrency, cache compatibility, the 170-test snapshot, measured
speedups and the unlimited A32 bottleneck. New citations include Etingof's MIT
notes (Proposition 32.1 and Corollary 35.9), official Sage dual/inner-product
documentation, SQLite WAL/datatypes and Python sqlite3 documentation. The
project-specific splitting heuristic and timings are identified as such.
Unrelated anomaly, Coulomb, Higgs-design and MySQL content remains unchanged.

The mathematical-background source is retained at the user's explicit request.
It embeds the preserved original pages 2-4 through the `source_assets` PDF;
only the obsolete JSON-cache sentence on original page 2 was changed. Keep
that asset with the TeX file when moving or rebuilding the document. Remaining
pages are editable LaTeX. `output/pdf/BUILD.md` records the two-pass build commands
and copies the background PDF to its canonical `index/` location. PDF outputs
are 28 and 13 pages respectively, and were rendered and visually checked, with no
overfull boxes or unresolved
citations. Nineteen unchanged summary pages were compared for identical body
text and equation numbering; background pages 3-4 were preserved completely.
No production code or live database was changed for this documentation update.

Claude's supplied audit used a different sandbox and a Sage replacement for
LiE. The current review reproduced its substantive findings, the FORM wildcard
substitution behavior, and the full/half and Casimir examples. Its independent
reference scripts, randomized cases, and 87-entry cache snapshot were not
provided, so those particular historical experiments were not certified by
this review. Agreement on tested cases is not a proof for arbitrary inputs.

The user also provided a FORM manual at:

```text
/home/subo-lee/문서/수업/2026년 1학기/form-5.0.0-manual.pdf
```

## Hall-Littlewood and Higgs-branch discussion (not implemented)

### States, primaries, and grading

Using the conventions of Gadde et al., arXiv:1110.3740, the index condition is
`E - 2*j2 - 2*R + r = 0`. The HL limit additionally imposes
`E +/- 2*j1 - 2*R - r = 0`, giving

```text
HL contributing states: E = 2R + r, j1 = 0, j2 = r.
Higgs-ring primaries:    E = 2R,     j1 = j2 = 0, r = 0.
```

Higgs primaries are scalar bottom components of `B-hat_R` multiplets. The HL
index can also receive contributions from other states, including descendants.
In an index trace, spin symbols denote Cartan eigenvalues; a claim that a state
is scalar requires the Lorentz representation to be trivial.

The paper's HL weight is `(-1)^F * tau^(2*(E-R))`. For Higgs primaries this is
`tau^E`; it is not an energy grading for every possible HL state. The paper uses
`t_paper = tau^2`, which is different from this project's `t`.

### Vector letter and F-term constraints

For full hypers and adjoint chiral field `Phi`, at zero masses and FI parameters:

```text
W = sqrt(2) sum_i Qtilde_i Phi Q_i
  = sqrt(2) sum_a Phi^a mu_C^a,
mu_C^a = sum_i Qtilde_i T^a Q_i.
```

On the Higgs branch set `Phi = 0`. The remaining F-terms are `mu_C^a = 0`,
quadratic moment-map equations in the gauge adjoint. Scalars have HL weight
`tau`; the equations have weight `tau^2 * chi_adj(z)`.

For the polynomial ring `S` of hyper scalars, quotienting by a regular homogeneous
equation of degree d and weight w multiplies its Hilbert series by
`1 - tau^d*w`. If the moment-map components form a regular sequence, their
combined factor is

```text
product_(adjoint weights w) (1 - tau^2*w) = PE[-tau^2*chi_adj(z)].
```

This matches the HL vector letter. The surviving vector fermion has
`(E,R,r,j1,j2) = (3/2,1/2,1/2,0,1/2)` and contributes `-tau^2` per adjoint
weight. For SU(2), the constraint factor is

```text
(1 - tau^2*a^2)(1 - tau^2)(1 - tau^2/a^2)
= 1 - tau^2*chi_3(a) + tau^4*chi_3(a) - tau^6.
```

The Koszul complex with formal odd variables `eta_a` and `d eta_a = mu_C^a`
has degree-zero homology `S/(mu_C)`. Its alternating character is the vector
factor times the free scalar series. Regularity makes higher Koszul homology
vanish. This condition concerns the equations before gauge projection; it does
not require the final ring of gauge invariants to be a complete intersection.

The HL integral is

```text
I_HL(tau,a) = integral_G dmu(z) PE[
    tau*chi_V(z,a) - tau^2*sum_gauge_factors chi_adj(z)
].
```

Here V contains every holomorphic hyper scalar, including both halves of each
full hyper. Gauge projection selects gauge invariants; it must not project
flavor factors. The formula equals the Higgs Hilbert series under suitable
conditions, including regularity as a sufficient condition in this setup.
Do not assume equality for every SCFT or for all genus-zero constructions.
Extra HL sectors can survive when the moment-map complex has higher homology.

### HL limit in the current project's variables

The existing full-index kernels are

```text
J = 1 / ((1 - t^3*y)*(1 - t^3/y))
K_hyp = J*(t^2/u - t^4*u)
K_vec = J*(t^2*u^2 - t^4/u^2 - t^3*y - t^3/y + 2*t^6).
```

Hold `tau = t^2/u` fixed and take `t -> 0`, with `u = t^2/tau` and fixed y.
Then `K_hyp -> tau` and `K_vec -> -tau^2`.

For an already computed full index:

```text
t^a*y^b*u^c -> t^(a+2c)*y^b*tau^(-c).
```

Terms with `a+2c=0` survive; terms with positive `a+2c` vanish; negative
`a+2c` indicates a divergent term. The surviving expression must be independent
of y. An input known through `t^N` can determine integer HL powers through
`tau^floor(N/2)`, provided it contains all coefficients through that order.

A direct HL calculation would reuse the FORM character expansion and LiE gauge
projection, replace kernels with `tau` and `-tau^2`, and truncate in tau.
The full-index builder's minimum-letter-degree assumptions (`order // 2`)
cannot be copied unchanged: an HL hyper letter has degree 1. This direct
approach avoids computing full-index terms that disappear in the limit.

### Unrefined versus flavor-refined Higgs data

For actual Higgs-ring operators:

```text
H(tau,a) = sum_(Delta,lambda) m_(Delta,lambda)*chi_lambda^F(a)*tau^Delta
H(tau,1) = sum_Delta N_Delta*tau^Delta,
N_Delta = sum_lambda m_(Delta,lambda)*dim(lambda).
```

Setting flavor fugacities to 1 preserves total operator counts, including
composites, and their dimensions. It does not select flavor singlets and it does
not change gauge projection. It loses flavor representation labels, which
generally cannot be reconstructed from the counts. For example, the SU(3),
six-flavor test's `36*t^4/u^2` becomes `36*tau^2`; refinement distinguishes
`(chi_35^SU(6) + 1)*tau^2`.

"Higgs spectrum" needs interpretation: coefficients of H count independent
ring operators, while primitive generators require further ring/PL analysis.
The signed PL includes relations and can include higher syzygies. Positive PL
terms are not universally new generators. A Hilbert series alone need not
uniquely determine a minimal ring presentation, even with flavor refinement.
The free Coulomb-spectrum extraction function should not be used as a general
Higgs-generator extractor. Its lower-level numerical PL machinery is reusable.

The advised minimal next step, if requested, is unrefined HL/Higgs calculation
with explicit treatment of when HL equals the Hilbert series. Flavor refinement
is optional if total dimension-by-dimension counts meet the user's needs.

Flavor refinement would require the following changes:

1. Reuse/extract flavor-block grouping from `common/n2_theory_properties.py`
   into a shared module to avoid circular imports (properties already imports
   index). Construct gauge-flavor tensor-product scalar representations.
2. Extend `CharacterSpec`/`_character_basis` to identify gauge versus flavor
   factors. For n full complex hypers replace numerical multiplicities with
   `chi_R^G*chi_n^U(n) + chi_Rbar^G*chi_nbar^U(n)`. For n real full hypers use
   the fundamental `2n` of Sp(n); for m pseudoreal half-hyper units use the
   vector m of SO(m). Track abelian flavor charges explicitly. The project
   variable u is an R-symmetry fugacity, not such a flavor variable.
3. Carry flavor formal characters through FORM with the same Adams index j as
   their paired gauge characters: `chi_R(z^j)*chi_F(a^j)`.
4. Modify `_project_terms` to take gauge singlets only and retain full flavor
   decompositions. Reuse `CharacterDecompositionCache` for supported simple
   flavor algebras and extend full tensor-product collection where needed;
   `singlet_multiplicities` alone cannot supply flavor output.
5. Extend output rings/parsers/serialization beyond numerical coefficients in
   `(t,y,u)`, or use sparse maps from degree to flavor Dynkin labels, abelian
   charges, and multiplicity, with factor metadata.
6. For refined PL apply Adams operations to flavor variables too:
   `sum_k mu(k)/k * log H(tau^k,a^k)`. Ordinary numerical PL coefficients
   cannot preserve flavor representation content.

No flavor-refinement implementation or option was added during this discussion.

### References consulted

- Gadde, Rastelli, Razamat, Yan, *Gauge Theories and Macdonald Polynomials*,
  https://arxiv.org/abs/1110.3740 — equations (2.10), (4.6)–(4.11), Table 2,
  and Appendix B for HL conditions, letters, and F-term interpretation.
- Kang et al., *Higgs, Coulomb, and Hall-Littlewood*,
  https://arxiv.org/abs/2207.05764 — counterexamples to general HL/Higgs equality,
  including some genus-zero twisted class-S theories.
- Hanany and Kalveks, *Highest Weight Generating Functions for Hilbert Series*,
  https://arxiv.org/abs/1408.4690 — character and highest-weight descriptions.
- Stacks Project, https://stacks.math.columbia.edu/tag/0669 — Koszul resolution
  of a quotient by a Koszul-regular sequence.

Temporary copies of the first paper were downloaded as
`/tmp/arxiv-1110.3740.pdf` and `/tmp/arxiv-1110.3740.txt`; these may not persist.

## Known limitations and useful next tasks

- Update the remaining implementation reference chapters for Tits reality,
  representation/theory enumeration and current dependencies; the database
  structure, schema-6 behavior and the current index/cache algorithm are documented.
- Optimize the expensive intermediate `psi_3(adjoint)^2` tensor decomposition
  identified in the unlimited A32 profile; final sparse pairing is inexpensive.
- Migrate existing database hashes and shared flavor labels if data stored
  under the previous conjugacy or full/half conventions must be reused; resolve
  any pre-existing duplicate theory rows during that migration.
- Implement HL/Higgs calculations if requested, following the qualifications
  and reuse opportunities above; flavor refinement remains optional.
- Handle database spectrum backfill explicitly for duplicate realizations or
  with a dedicated migration/backfill operation.
- Add non-Lagrangian theory support beyond the placeholder table.
- Avoid the duplicate anomaly-check call in the database/property path.
- Move duplicate detection before expensive index calculation.
- Make the canonical hash invariant under product-factor permutations.
- Add automatic or assisted identification of dual Lagrangian realizations.
- Run and strengthen live MySQL integration tests.
- Consider storing index monomials structurally if database-level coefficient
  queries become necessary.
- Retain the source cutoff when using truncated indices; generated Coulomb
  series currently lack an `O(...)` precision marker.
- Preserve the type-A highest-weight projection when refactoring Casimirs.
- FORM treats nonempty stderr as failure, and LiE parsing accepts only its
  expected output plus a recognized tree-space notice. This is a tool-version
  compatibility concern, not a demonstrated incorrect result.

`main.py` is currently a six-line stub that prints `sys.version`. OR-Tools is
used by the live Frobenius solver in `common/math_utils.py`, not by this stub.
