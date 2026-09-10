# Character-cache split selection: temporary prototype comparison

The candidate was implemented and tested under `/tmp/sci-adams-cache-candidate/` before promotion to `index/char_decomposition_cache.py`. Snapshots of the baseline and candidate, the comparison script, and individual measurements are retained here.

The new split selection helps when two cached blocks avoid intermediate decompositions. These targeted misses improved; the full-index workloads showed no consistent overall speedup.

## Changes

- Return the known first Adams operation and trivial-representation decompositions without LiE.
- Preserve the usual recursion when both its dependencies are available. Otherwise find pairs of cached products for the same algebra and representation whose exponent vectors sum to the requested vector.
- Rank alternative cached pairs using the product of their numbers of irreducible terms, with scalar and zero factors handled without LiE. This is a heuristic, not a guarantee of the fastest tensor product.
- Use the same selection in the batch dependency scheduler and during calculation, including worker processes. Reuse the existing tensor helper.
- Preserve the SQLite schema and keys. Cache misses still execute outside write transactions, and connections/state remain local to each thread/process.

## Targeted persisted-cache misses

Five alternating baseline/candidate trials per case and API. Each starts from a separate identical copy of a prepared SQLite database; seed preparation and copying are excluded. Times include opening/closing the cache and persisting the new results.

For the first five cases, psi_1(R)^2 and psi_2(R)^2 are cached and psi_1(R)^2 psi_2(R)^2 is requested. The last case keeps only the decompositions of psi_2(R)^2 and psi_3(R)^2, deletes their atomic prerequisites, and requests their product.

| Representation / cache state | Single old (ms) | Single new (ms) | Speedup | Batch old (ms) | Batch new (ms) | Speedup |
|---|---:|---:|---:|---:|---:|---:|
| SU(2) fundamental | 29.26 | 21.25 | 1.38x | 22.79 | 21.33 | 1.07x |
| SU(3) adjoint | 29.30 | 21.42 | 1.37x | 23.03 | 21.48 | 1.07x |
| Sp(2) fundamental | 29.06 | 21.05 | 1.38x | 22.92 | 21.51 | 1.07x |
| G2 fundamental | 29.12 | 21.25 | 1.37x | 23.28 | 21.58 | 1.08x |
| SU(5) adjoint | 29.04 | 22.16 | 1.31x | 23.19 | 22.53 | 1.03x |
| SU(2), only composite rows retained | 36.35 | 21.19 | 1.72x | 24.46 | 20.93 | 1.17x |

Tensor calls decreased from two to one in every targeted case. In the composite-only case Adams calls also decreased from one to zero. The batch API buffers intermediate writes, so its improvement is smaller than the single-request API.

## Full indices through t^18

Six theories, two character-cache states, three alternating trials per implementation: 72 timed full calculations. All use a prefilled FORM cache and an unavailable FORM executable, so FORM execution is excluded equally from both versions. Cold means an initialized empty character cache. From t^12 means the same baseline-generated cache populated by calculating the theory through t^12. Python/Sage startup, seed preparation and copying are excluded. Times are medians in seconds.

| Theory | Character cache | Old (s) | New (s) | Old / new | Adams calls old/new | Tensor calls old/new |
|---|---|---:|---:|---:|---:|---:|
| SU(2), 4 fundamentals | cold | 0.270 | 0.282 | 0.959x | 18/16 | 87/87 |
| SU(2), 4 fundamentals | from_t12 | 0.237 | 0.210 | 1.129x | 6/6 | 76/76 |
| SU(3), 6 fundamentals | cold | 0.841 | 0.836 | 1.006x | 27/24 | 286/286 |
| SU(3), 6 fundamentals | from_t12 | 0.776 | 0.799 | 0.971x | 9/9 | 268/268 |
| SU(5), 10 fundamentals | cold | 0.872 | 0.871 | 1.001x | 27/24 | 286/286 |
| SU(5), 10 fundamentals | from_t12 | 0.805 | 0.797 | 1.010x | 9/9 | 268/268 |
| Sp(2), 6 fundamentals | cold | 0.294 | 0.283 | 1.038x | 18/16 | 87/87 |
| Sp(2), 6 fundamentals | from_t12 | 0.244 | 0.245 | 0.993x | 6/6 | 76/76 |
| G2, 4 fundamentals | cold | 0.260 | 0.251 | 1.037x | 18/16 | 66/66 |
| G2, 4 fundamentals | from_t12 | 0.223 | 0.214 | 1.044x | 6/6 | 58/58 |
| SU(5), symmetric + antisymmetric | cold | 4.559 | 4.554 | 1.001x | 45/40 | 977/977 |
| SU(5), symmetric + antisymmetric | from_t12 | 4.415 | 4.323 | 1.021x | 15/15 | 951/951 |

Most full-index differences are within a few percent and vary in direction. The largest changes were a 4.3% slowdown and an 11.4% time reduction; these are small-sample measurements, not evidence of a consistent end-to-end improvement. For these full-index workloads the tensor-call counts were identical. Cold runs save the one Adams(1,R) call per formal representation; fully populated caches do not execute this planning path at all.

## Exactness and concurrency

- All targeted decompositions agreed exactly with the baseline. SU(2) cases also matched an independent weight-expansion oracle.
- 130 products across SU(2), SU(3) fundamental/adjoint, Sp(2), and G2 agreed exactly in serial and three-worker batch generation. This matrix uses Adams indices up to four and weighted order up to six.
- All 72 full-index calculations matched both implementations and the retained earlier index coefficients exactly.
- Regression coverage checks persisted composite rows without atomic prerequisites, avoiding unused batch dependencies, choosing among cached pairs, three-worker generation, visibility of another connection's writes, first-Adams/trivial identities, and higher atomic Adams calls.
- Existing tests additionally cover shared-client threads, independent writer processes, signed decompositions, empty results, cache reopening and exact singlet projection.

Full project validation after promotion: **197 tests run, 195 passed, 2 MySQL tests skipped** (14.539 seconds). The focused character-cache, projection and index suite also passed all 44 tests.

## Reproduce

Run these separately from the project root with Sage Python. Inputs for the full-index suite come from the retained `form_expansion_theories/results.json` and its prefilled FORM database. All new databases are temporary.

```bash
DOT_SAGE=/tmp/codex-sage-cache PYTHONDONTWRITEBYTECODE=1 /home/subo-lee/miniconda3/envs/sage/bin/sage -python -B output/benchmarks/adams_cache_planner/benchmark.py --suite decomposition --api single
DOT_SAGE=/tmp/codex-sage-cache PYTHONDONTWRITEBYTECODE=1 /home/subo-lee/miniconda3/envs/sage/bin/sage -python -B output/benchmarks/adams_cache_planner/benchmark.py --suite decomposition --api batch
DOT_SAGE=/tmp/codex-sage-cache PYTHONDONTWRITEBYTECODE=1 /home/subo-lee/miniconda3/envs/sage/bin/sage -python -B output/benchmarks/adams_cache_planner/benchmark.py --suite index
```

The first single-request measurements are in `decomposition-temporary.json`; rerunning writes `decomposition-single-temporary.json`. The full-index script also writes `index-temporary.json` after each completed scenario. All timings use one calculation worker unless explicitly labelled parallel, normal garbage collection, and warm filesystem caches; the compared implementations run sequentially.
