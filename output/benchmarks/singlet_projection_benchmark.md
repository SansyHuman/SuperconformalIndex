# Singlet projection benchmark — 2026-09-09

The temporary implementation matched the previous SQLite implementation exactly
and improved cold index calculation before it replaced the production code.
Baseline: git commit `a9b70093dfe3c16b4710c347f75e985e446b8f87`.
This measures the projection optimization separately from the earlier JSON-to-SQLite migration.

## Algorithm and scope

Split each character monomial into two partial products before decomposing it.
If `A = sum a_lambda chi_lambda` and `B = sum b_mu chi_mu`, then
`[1](A*B) = sum_lambda a_lambda b_(lambda dual)`. The final operation is a sparse
lookup and signed integer sum. Actual conjugate orientations are preserved;
pseudoreal representations pair with themselves without a minus sign.

The split treats each Adams operation as an indivisible factor, balancing the
approximate costs `j * sum(Dynkin labels)`. Partial products of a single base
irrep use the existing SQLite decomposition cache and process pool. Mixed
partial products are memoized in thread-local memory. Intermediate products
may still need full LiE decomposition, but the complete product is never
tensor-decomposed by the singlet path. Single Adams operations still require
their character decomposition. The explicitly requested full-decomposition API
remains available.

SQLite schema version 1, canonical keys, and default database path are unchanged.
Existing singlet entries remain valid; no cache migration is needed.

## Measurement method

The candidate was written under `/tmp/sci-singlet-projection/candidate` and
compared with frozen source under `/tmp/sci-singlet-projection/baseline` before
promotion. Sage Python 3.11.16, FORM `/usr/bin/form`, LiE `/usr/bin/lie`, local
SQLite files. No production cache was used. The tables report wall-clock seconds.

Each backend and trial starts with a fresh SQLite database. The warm phase uses
a new cache client against that trial's persisted data. Backend order alternates
between trials. Algebra initialization is shared outside timing. Projection
measurements exclude the shared FORM expansion; they include singlet projection,
final Sage polynomial assembly and cache close. Full-index measurements include
input validation, FORM, parsing, projection and result assembly. Equality checks
compare exact Laurent-polynomial coefficient dictionaries, with no rounding.

## Projection: medians of three trials, one worker

Type-A cases are SU(rank+1) SQCD with `2*(rank+1)` full fundamental hypers.
The two-factor case has two full bifundamentals; the three-factor case has two
half trifundamentals. The suffix `tN` denotes truncation through `t^N`.

| Case | Previous cold (s) | New cold (s) | Speedup | Previous warm (s) | New warm (s) |
|---|---:|---:|---:|---:|---:|
| A1-t18 | 0.4182 | 0.2506 | 1.67x | 0.0250 | 0.0271 |
| A2-t12 | 0.2249 | 0.1785 | 1.26x | 0.0114 | 0.0105 |
| A8-t18 | 4.5993 | 0.8486 | 5.42x | 0.1071 | 0.1075 |
| A16-t12 | 1.4728 | 0.2068 | 7.12x | 0.0124 | 0.0128 |
| A32-t8 | 0.4689 | 0.1168 | 4.01x | 0.0029 | 0.0028 |
| A1xA1-t12 | 0.1534 | 0.1116 | 1.37x | 0.0090 | 0.0091 |
| A1xA1xA1-half-t10 | 0.1158 | 0.0923 | 1.25x | 0.0073 | 0.0073 |

All 84 evaluations across these seven cases agreed exactly. Warm-cache
performance is effectively unchanged; both implementations bypass decomposition
when a singlet coefficient is already present.

## Complete index: medians of three trials, one worker

| Case | Previous cold (s) | New cold (s) | Speedup | Previous warm (s) | New warm (s) |
|---|---:|---:|---:|---:|---:|
| A8-t18 | 6.2134 | 2.4427 | 2.54x | 1.6947 | 1.6987 |

All 12 evaluations agreed exactly. The cold complete-index speedup is 2.54x.
FORM now accounts for a larger fraction of the runtime in this case.

## Production check: one trial, four workers

After promotion, the reusable benchmark was run against the same git baseline.
All 28 evaluations agreed exactly. These single trials verify multiprocessing
and show its overhead; they are not three-trial performance estimates.

| Case | Previous cold (s) | New cold (s) | Speedup | Previous warm (s) | New warm (s) |
|---|---:|---:|---:|---:|---:|
| A1-t18 | 0.3058 | 0.2674 | 1.14x | 0.0254 | 0.0264 |
| A2-t12 | 0.2014 | 0.2043 | 0.99x | 0.0109 | 0.0105 |
| A8-t18 | 3.6011 | 0.8208 | 4.39x | 0.1082 | 0.1046 |
| A16-t12 | 1.3495 | 0.2364 | 5.71x | 0.0125 | 0.0132 |
| A32-t8 | 0.4706 | 0.1527 | 3.08x | 0.0028 | 0.0032 |
| A1xA1-t12 | 0.1719 | 0.1554 | 1.11x | 0.0090 | 0.0092 |
| A1xA1xA1-half-t10 | 0.1506 | 0.1670 | 0.90x | 0.0072 | 0.0071 |

Small cases can spend more time on process startup and mixed-partial LiE calls;
the two small regressions here were approximately 3 ms and 16 ms. The high-rank
cases retained substantial speedups. More processes are not automatically faster.

## Higher-rank probes and limitations

- A16 SQCD through `t^18`: new cold projection 1.9250 s, warm 0.1405 s;
  the previous code exceeded the 25-second operation limit.
- A32 SQCD through `t^12`: new cold projection 0.5104 s, warm 0.0141 s.
  The previous implementation was not run at this order in this benchmark.
- A32 SQCD through `t^18`: the new code also exceeded 25 seconds while
  calculating an intermediate decomposition.

The completed new probe results matched their own warm-cache results. They do
**not** provide complete old/new equality comparisons. The replacement decision
uses the seven completed comparative cases and independent checks above/below.
The greedy split is a heuristic; expensive partial decompositions still exist.

## Correctness and compatibility

Before promotion:

- 319 singlet queries matched the previous implementation. These include complex,
  real and pseudoreal examples, negative virtual-character coefficients, mixed
  products and all supported Cartan families.
- 202 of those queries also matched independent SU(2) weight-difference or SU(3)
  Weyl constant-term calculations.
- 216 random dual-label comparisons matched Sage across 18 Cartan types:
  A1, A2, A3, A8, A16, A32, B2, B3, C2, C3, D4, D5, D6, E6, E7, E8, F4, G2.
- 4,996 previous SQLite singlet entries were reused with the calculation routine
  disabled, verifying unchanged keys and cache compatibility.

Seven permanent regression tests cover direct complex/pseudoreal pairing without
LiE, arbitrary-size coefficients, splitting grouped Adams factors before full
decomposition, products with three or more factors, independent SU(2)/SU(3)
weights, serial/parallel generation, trivial characters and zeros. The
`psi_4(adj) * psi_5(adj)` A8 test checks coefficient 12 while allowing only the
two individual Adams decompositions and forbidding the final tensor product.

After promotion, the full suite ran 170 tests in 11.461 s: 168 passed and two
live-MySQL tests were skipped. No live database tests were run.

## Reproduce

Run from the project root with Sage Python. Choose an unused output directory.
The original JSON-cache comparison remains available with the runner's defaults.
For this optimization use the SQLite baseline and labels explicitly:

```bash
DOT_SAGE=/tmp/codex-sage-cache \
/home/subo-lee/miniconda3/envs/sage/bin/sage -python -B \
  test/benchmark_character_cache.py \
  --baseline-ref a9b7009 --baseline-label existing --candidate-label sparse \
  --output-directory /tmp/singlet-projection-recheck \
  --suite projection --workers 1 --rounds 3
```

Use `--suite full` and a different output directory for the complete A8 index.
The temporary prototype and comparison scripts remain under
`/tmp/sci-singlet-projection`; that directory is scratch space, not permanent
project storage. Durable timings are in `singlet_projection_timings.json`, and
regressions are in `test/test_singlet_projection.py`.
