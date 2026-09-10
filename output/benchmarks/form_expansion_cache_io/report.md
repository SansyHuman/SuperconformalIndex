# FORM expansion cache I/O benchmark

Measured at 2026-09-10T07:22:27.048802+00:00 using the existing cached order-t^18 FORM program.

The expansion has 113,831 terms. The raw program is 589 bytes; JSON is 5,907,568 bytes (5.91 MB), and the closed single-entry SQLite database is 5,922,816 bytes.

Each operation has 30 measured trials after 3 warmups. All times are milliseconds. Save/load component totals are calculated within each trial before taking the median; medians of separate components need not add exactly.

| Operation | Median (ms) | 10th–90th percentile (ms) |
|---|---:|---:|
| Serialize terms to JSON | 179.32 | 173.37–215.43 |
| SQLite INSERT and COMMIT | 42.07 | 33.88–42.71 |
| Save total (serialize + write) | 221.51 | 214.09–257.48 |
| SQLite SELECT and fetch JSON | 3.08 | 2.82–3.13 |
| Deserialize JSON to IndexFormTerm objects | 866.42 | 781.50–1063.97 |
| Load components combined | 869.23 | 784.59–1067.01 |
| Actual get_expansion, open connection | 870.81 | 771.56–1057.39 |
| Actual get_expansion, new connection including close | 894.65 | 810.44–1102.57 |
| Initialize a new database (separate from save) | 31.43 | 31.16–31.91 |

Saving an already-calculated expansion takes approximately 0.22 seconds. Loading through a newly created cache client takes approximately 0.90 seconds. Reconstructing Python objects dominates the load time; SQLite itself takes about 3 ms to retrieve the JSON.

## Conditions

- One existing entry; no FORM execution or parsing is timed.
- Each insert commits a real row in a newly initialized temporary database.
- Save total is serialization plus INSERT and COMMIT; initialization is separate.
- Read trials use warm OS file caches, with garbage collection enabled.
- New-connection hits include cache construction, connect, schema check, read, decode and close.
- Single process, no competing benchmark writers; concurrent contention is not measured.
- Every restored expansion is checked for exact equality outside the timed region.
- Temporary databases were on the project filesystem: ext4 on /dev/nvme0n1p7. The existing cache was opened read-only.
- SQLite 3.53.4; journal_mode=wal; synchronous=2 (FULL); page_size=4096; wal_autocheckpoint=1000 pages. These are the current implementation's settings.
- Python: 3.11.16 | packaged by conda-forge | (main, Aug 21 2026, 22:44:51) [GCC 14.4.0]; platform: Linux-6.8.0-139-generic-x86_64-with-glibc2.39.
- These results characterize this expansion and this machine. They do not measure cold storage reads or concurrent lock contention.

## Reproduce

From the project root:

```bash
DOT_SAGE=/tmp/codex-sage-cache PYTHONDONTWRITEBYTECODE=1 /home/subo-lee/miniconda3/envs/sage/bin/sage -python -B output/benchmarks/form_expansion_cache_io/benchmark.py
```

The script benchmarks the largest entry in the source database; pass `--source /path/to/cache.db` to choose another database. The exact program and every individual timing sample are retained in [timings.json](timings.json).
