# Cross-theory FORM cache reuse

Verified using current generated programs, fresh temporary FORM databases, and a prefilled character-cache copy with writes and LiE disabled.

| Theory populating cache | Different theory reusing it | Order | FORM calls on reuse | Rows after reuse | Independent index matches |
|---|---|---:|---:|---:|---|
| SU(2), 4 fundamental hypers | G2, 4 fundamental hypers | 12 | 0 | 1 | Yes |
| G2, 4 fundamental hypers | SU(2), 4 fundamental hypers | 12 | 0 | 1 | Yes |
| SU(2), 4 fundamental hypers | G2, 4 fundamental hypers | 18 | 0 | 1 | Yes |
| G2, 4 fundamental hypers | SU(2), 4 fundamental hypers | 18 | 0 | 1 | Yes |
| Sp(2) = USp(4), 6 fundamental hypers | Spin(8), 6 vector hypers | 12 | 0 | 1 | Yes |
| Spin(8), 6 vector hypers | Sp(2) = USp(4), 6 fundamental hypers | 12 | 0 | 1 | Yes |
| Sp(2) = USp(4), 6 fundamental hypers | Spin(8), 6 vector hypers | 18 | 0 | 1 | Yes |
| Spin(8), 6 vector hypers | Sp(2) = USp(4), 6 fundamental hypers | 18 | 0 | 1 | Yes |

For each row, the first theory executed FORM exactly once. The second theory used a new cache client, executed and parsed FORM zero times, and decoded the persisted expansion once. The single stored row was unchanged. An independent FORM calculation of the second theory produced exactly the same index and serialized expansion. The two theories' final indices differed, confirming that their gauge projections remain distinct. A different raw-program control correctly missed the cache.

The same complete program text shares one cache entry regardless of gauge group or representation metadata. Reuse requires a common FORM database. Whitespace, numerical matter multiplicities, truncation order, and character naming/order are part of the exact key; no symbolic equivalence check is performed.

Run with Sage's Python:

```bash
DOT_SAGE=/tmp/codex-sage-cache PYTHONDONTWRITEBYTECODE=1 /home/subo-lee/miniconda3/envs/sage/bin/sage -python -B output/benchmarks/form_expansion_theories/check_cross_theory_reuse.py
```

Exact inputs, shared programs, and differing coefficient examples are retained in [cross_theory_reuse.json](cross_theory_reuse.json).
