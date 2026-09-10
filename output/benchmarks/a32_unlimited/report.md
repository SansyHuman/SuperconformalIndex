# A32 unlimited index profile — 2026-09-10

The A32 SQCD index through `t^18` completed successfully. The theory is SU(33)
with 66 full fundamental hypermultiplets, matching the previously timed-out
benchmark. This is not a test of every A32 matter content or every truncation.

## Run configuration

Current production implementation, Sage Python, FORM and LiE, one decomposition
worker (`processes=1`), and `timeout=None` for both FORM and LiE. No alarm or
overall computation deadline was installed. A new SQLite database under
`/tmp/sci-a32-unlimited/cache.db` supplied the cold cache; the project-root DB
was not used. The warm run created a new cache client against this same file,
within the same Sage process. Instrumentation was confined to a temporary
profiling script; production source was not modified.

One worker makes the stage timings comparable to the previous single-worker
benchmark. These measurements do not characterize the default worker count.
Each timing is a single wall-clock measurement, not a multi-run median.
Python/Sage import time is outside the timed `calculate_index` call; cold algebra
initialization inside input parsing is included. The measured LiE calls include
subprocess startup and communication.

## Result and non-overlapping stage timings

| Stage | Cold (s) | Warm (s) |
|---|---:|---:|
| Input parsing, validation and algebra initialization | 4.483 | 0.009 |
| FORM expansion | 1.357 | 1.406 |
| Parsing FORM output | 0.212 | 0.239 |
| Singlet projection, including cache operations | 88.229 | 0.127 |
| Final Sage polynomial assembly | 0.002 | 0.001 |
| Complete calculation | **94.293** | **1.786** |

Small setup/close costs account for the difference between the listed stages
and the complete calculation. FORM produced 20,640 intermediate terms. The
final Laurent polynomial has 117 nonzero monomials. Exact coefficient
dictionaries from the cold and warm runs match; this is a cache-consistency
check, not an independent mathematical derivation of all coefficients.
The output is retained in `index_cold.txt` and `results.json`.

## Main bottleneck

A single LiE call fully decomposing `psi_3(adjoint) * psi_3(adjoint)` took
**82.699 seconds**, or **87.7% of the complete cold calculation** and **93.7% of
singlet projection**. Each input Adams decomposition contains 10 nonzero irrep
terms; the resulting intermediate decomposition contains 91 nonzero terms.
The Python request is:

```python
cache.get_decomposition('A32', (1,) + (0,) * 30 + (1,), (0, 0, 2))
```

The input label `(1,0,...,0,1)` denotes the adjoint. The powers `(0,0,2)` mean
two third-Adams factors, not a sixth Adams operation. The canonical stored
power vector is `(0,0,2,0,0,0)`.

This intermediate is needed even though the final singlet uses sparse dual
pairing. For example, `psi_3(adjoint)^3` splits into a two-factor part and a
one-factor part. The code must currently fully decompose the two-factor part
before contracting with the third factor. Avoiding the complete product's
decomposition therefore does not remove this intermediate calculation.

Across the cold run, all 313 LiE calls together took **87.764 seconds** (93.1%
of the total). All other LiE calls combined took **5.066 seconds**. The next
slowest individual call took about 0.392 seconds. The complete batch of 89
same-base-irrep decomposition requests took 83.676 seconds; the 224 mixed
intermediate tensor calls took 4.162 seconds. These are nested measurements
within projection and must not be added again to the main stage table.

The final sparse contraction and surrounding Python/cache work are not the
main cost: projection minus total LiE time is about 0.465 seconds. This combined
remainder was not separately divided into SQLite, planning and contraction.
The warm run made zero LiE calls. FORM then became the largest stage at 1.406
seconds out of 1.786 seconds.

The next performance target is this remaining intermediate tensor decomposition.
Increasing process count can overlap other requests but does not split this
single LiE request in the current implementation. No further optimization was
implemented during this diagnostic run.

## Artifacts and reproduction

- `summary.json`: aggregate measurements.
- `events.jsonl`: start/end timings and exact LiE expressions.
- `results.json`: total times and exact index coefficients.
- `index_cold.txt`, `index_warm.txt`: readable index outputs.
- `profile_index.py`: the exact temporary instrumentation used for this run.

The copied profiling script has `/tmp/sci-a32-unlimited` hardcoded as its output
and cache directory. To repeat a **cold** profile, copy the script and change
`OUT` to a fresh directory (create it first); otherwise it will reuse the
existing cache. Run with:

```bash
DOT_SAGE=/tmp/codex-sage-cache \
/home/subo-lee/miniconda3/envs/sage/bin/sage -python -B /path/to/profile_index.py
```
