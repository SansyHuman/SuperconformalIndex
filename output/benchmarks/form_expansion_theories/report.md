# Full-index benchmark with a prefilled character cache

All matter entries are full hypermultiplets. Every theory passes the current input/anomaly and vanishing-beta checks.

5 measured repetitions per mode, after 1 warmup cycle(s); medians in seconds. Mode order rotates between rounds. Each calculation opens new cache clients.

| Theory | Order | FORM terms | Cache disabled | Cache miss + save | Cache hit | Disabled / hit |
|---|---:|---:|---:|---:|---:|---:|
| SU(2), 4 fundamental hypers | 12 | 698 | 0.0295 | 0.0495 | 0.0054 | 5.43x |
| SU(2), 4 fundamental hypers | 18 | 6,771 | 0.4323 | 0.4916 | 0.0617 | 7.00x |
| SU(3), 6 fundamental hypers | 12 | 1,601 | 0.0763 | 0.0981 | 0.0133 | 5.75x |
| SU(3), 6 fundamental hypers | 18 | 20,640 | 1.7220 | 1.7959 | 0.2304 | 7.48x |
| SU(5), 10 fundamental hypers | 12 | 1,601 | 0.0749 | 0.0985 | 0.0139 | 5.40x |
| SU(5), 10 fundamental hypers | 18 | 20,640 | 1.7265 | 1.7839 | 0.2648 | 6.52x |
| SU(3), 1 adjoint hyper (N=4) | 12 | 583 | 0.0241 | 0.0442 | 0.0036 | 6.68x |
| SU(3), 1 adjoint hyper (N=4) | 18 | 4,600 | 0.2808 | 0.3180 | 0.0429 | 6.54x |
| Sp(2) = USp(4), 6 fundamental hypers | 12 | 698 | 0.0293 | 0.0502 | 0.0071 | 4.15x |
| Sp(2) = USp(4), 6 fundamental hypers | 18 | 6,771 | 0.4434 | 0.4817 | 0.0634 | 7.00x |
| Spin(8), 6 vector hypers | 12 | 698 | 0.0308 | 0.0514 | 0.0073 | 4.23x |
| Spin(8), 6 vector hypers | 18 | 6,771 | 0.4329 | 0.4848 | 0.0655 | 6.60x |
| G2, 4 fundamental hypers | 12 | 698 | 0.0291 | 0.0496 | 0.0073 | 3.96x |
| G2, 4 fundamental hypers | 18 | 6,771 | 0.4418 | 0.4874 | 0.0640 | 6.90x |
| SU(2) x SU(2), 2 bifundamental hypers | 12 | 2,075 | 0.1102 | 0.1317 | 0.0159 | 6.92x |
| SU(2) x SU(2), 2 bifundamental hypers | 18 | 28,154 | 2.7421 | 2.7843 | 0.3251 | 8.44x |
| SU(5), 1 symmetric + 1 antisymmetric hyper | 12 | 5,691 | 0.3665 | 0.4153 | 0.1136 | 3.23x |
| SU(5), 1 symmetric + 1 antisymmetric hyper | 18 | 113,831 | 13.7565 | 14.1896 | 1.8771 | 7.33x |

## Method

- Full calculate_index wall time; Python/Sage startup, benchmark setup, prefilling and equality checks are excluded.
- Before timing each case/order, a full calculation fills the character decomposition and final singlet caches. These rows remain unchanged during its timings.
- During timing the character DB is query-only, LiE and direct decomposition entry points raise errors, and any missing singlet would require a forbidden write. Each successful timing therefore uses a fully prefilled character cache.
- Disabled mode bypasses FORM SQLite entirely and runs the same FORM executor/parser; miss and hit use the current get_expansion implementation.
- Miss mode starts with an initialized empty FORM database for each trial; its time includes JSON serialization and durable insertion. Clearing that database is outside the timer.
- Hit mode reuses a populated FORM SQLite database and sets an unavailable FORM executable as a safeguard. Every hit executes and parses FORM zero times.
- All modes use processes=1, new cache clients per calculation, normal garbage collection, warm OS file caches, and no competing benchmark workers.
- Every result is checked for exact Laurent-polynomial equality to the prefill result outside the timer. Prefilled-cache row counts are also checked before and after each case/order.
- Timing and mode-selection instrumentation is confined to this benchmark script; no application source is changed.
- Both benchmark databases reside on the project filesystem; SQLite uses the application's WAL and default synchronous settings.

## Detailed stages

Stage medians are measured independently and may not sum exactly to the total. FORM-stage time includes its cache lookup/write as applicable; the full total also includes input validation, program construction, cache closure, projection and Sage polynomial construction.

| Theory | Order | Mode | Full total | FORM execute | FORM parse | JSON encode | JSON decode | FORM stage total | Projection |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| SU(2), 4 fundamental hypers | 12 | disabled | 0.0295 | 0.0195 | 0.0053 | 0.0000 | 0.0000 | 0.0252 | 0.0035 |
| SU(2), 4 fundamental hypers | 12 | miss | 0.0495 | 0.0196 | 0.0054 | 0.0006 | 0.0000 | 0.0389 | 0.0034 |
| SU(2), 4 fundamental hypers | 12 | hit | 0.0054 | 0.0000 | 0.0000 | 0.0000 | 0.0011 | 0.0013 | 0.0033 |
| SU(2), 4 fundamental hypers | 18 | disabled | 0.4323 | 0.3383 | 0.0567 | 0.0000 | 0.0000 | 0.4073 | 0.0234 |
| SU(2), 4 fundamental hypers | 18 | miss | 0.4916 | 0.3534 | 0.0776 | 0.0065 | 0.0000 | 0.4594 | 0.0233 |
| SU(2), 4 fundamental hypers | 18 | hit | 0.0617 | 0.0000 | 0.0000 | 0.0000 | 0.0349 | 0.0367 | 0.0231 |
| SU(3), 6 fundamental hypers | 12 | disabled | 0.0763 | 0.0526 | 0.0133 | 0.0000 | 0.0000 | 0.0661 | 0.0094 |
| SU(3), 6 fundamental hypers | 12 | miss | 0.0981 | 0.0532 | 0.0131 | 0.0018 | 0.0000 | 0.0806 | 0.0097 |
| SU(3), 6 fundamental hypers | 12 | hit | 0.0133 | 0.0000 | 0.0000 | 0.0000 | 0.0028 | 0.0030 | 0.0094 |
| SU(3), 6 fundamental hypers | 18 | disabled | 1.7220 | 1.4013 | 0.2114 | 0.0000 | 0.0000 | 1.6102 | 0.0947 |
| SU(3), 6 fundamental hypers | 18 | miss | 1.7959 | 1.3805 | 0.2379 | 0.0231 | 0.0000 | 1.6665 | 0.0950 |
| SU(3), 6 fundamental hypers | 18 | hit | 0.2304 | 0.0000 | 0.0000 | 0.0000 | 0.1306 | 0.1327 | 0.0931 |
| SU(5), 10 fundamental hypers | 12 | disabled | 0.0749 | 0.0507 | 0.0128 | 0.0000 | 0.0000 | 0.0640 | 0.0098 |
| SU(5), 10 fundamental hypers | 12 | miss | 0.0985 | 0.0530 | 0.0131 | 0.0020 | 0.0000 | 0.0808 | 0.0100 |
| SU(5), 10 fundamental hypers | 12 | hit | 0.0139 | 0.0000 | 0.0000 | 0.0000 | 0.0028 | 0.0031 | 0.0098 |
| SU(5), 10 fundamental hypers | 18 | disabled | 1.7265 | 1.3823 | 0.2394 | 0.0000 | 0.0000 | 1.6226 | 0.1018 |
| SU(5), 10 fundamental hypers | 18 | miss | 1.7839 | 1.3948 | 0.2373 | 0.0243 | 0.0000 | 1.6732 | 0.0995 |
| SU(5), 10 fundamental hypers | 18 | hit | 0.2648 | 0.0000 | 0.0000 | 0.0000 | 0.1605 | 0.1630 | 0.0975 |
| SU(3), 1 adjoint hyper (N=4) | 12 | disabled | 0.0241 | 0.0167 | 0.0042 | 0.0000 | 0.0000 | 0.0211 | 0.0018 |
| SU(3), 1 adjoint hyper (N=4) | 12 | miss | 0.0442 | 0.0173 | 0.0040 | 0.0008 | 0.0000 | 0.0350 | 0.0018 |
| SU(3), 1 adjoint hyper (N=4) | 12 | hit | 0.0036 | 0.0000 | 0.0000 | 0.0000 | 0.0008 | 0.0010 | 0.0016 |
| SU(3), 1 adjoint hyper (N=4) | 18 | disabled | 0.2808 | 0.2315 | 0.0346 | 0.0000 | 0.0000 | 0.2689 | 0.0097 |
| SU(3), 1 adjoint hyper (N=4) | 18 | miss | 0.3180 | 0.2330 | 0.0351 | 0.0046 | 0.0000 | 0.2985 | 0.0100 |
| SU(3), 1 adjoint hyper (N=4) | 18 | hit | 0.0429 | 0.0000 | 0.0000 | 0.0000 | 0.0288 | 0.0308 | 0.0097 |
| Sp(2) = USp(4), 6 fundamental hypers | 12 | disabled | 0.0293 | 0.0193 | 0.0055 | 0.0000 | 0.0000 | 0.0250 | 0.0035 |
| Sp(2) = USp(4), 6 fundamental hypers | 12 | miss | 0.0502 | 0.0197 | 0.0055 | 0.0009 | 0.0000 | 0.0389 | 0.0037 |
| Sp(2) = USp(4), 6 fundamental hypers | 12 | hit | 0.0071 | 0.0000 | 0.0000 | 0.0000 | 0.0011 | 0.0028 | 0.0034 |
| Sp(2) = USp(4), 6 fundamental hypers | 18 | disabled | 0.4434 | 0.3415 | 0.0581 | 0.0000 | 0.0000 | 0.4172 | 0.0246 |
| Sp(2) = USp(4), 6 fundamental hypers | 18 | miss | 0.4817 | 0.3341 | 0.0810 | 0.0074 | 0.0000 | 0.4475 | 0.0250 |
| Sp(2) = USp(4), 6 fundamental hypers | 18 | hit | 0.0634 | 0.0000 | 0.0000 | 0.0000 | 0.0355 | 0.0377 | 0.0242 |
| Spin(8), 6 vector hypers | 12 | disabled | 0.0308 | 0.0203 | 0.0055 | 0.0000 | 0.0000 | 0.0262 | 0.0037 |
| Spin(8), 6 vector hypers | 12 | miss | 0.0514 | 0.0203 | 0.0053 | 0.0011 | 0.0000 | 0.0400 | 0.0037 |
| Spin(8), 6 vector hypers | 12 | hit | 0.0073 | 0.0000 | 0.0000 | 0.0000 | 0.0012 | 0.0029 | 0.0035 |
| Spin(8), 6 vector hypers | 18 | disabled | 0.4329 | 0.3304 | 0.0598 | 0.0000 | 0.0000 | 0.3954 | 0.0250 |
| Spin(8), 6 vector hypers | 18 | miss | 0.4848 | 0.3422 | 0.0801 | 0.0072 | 0.0000 | 0.4397 | 0.0252 |
| Spin(8), 6 vector hypers | 18 | hit | 0.0655 | 0.0000 | 0.0000 | 0.0000 | 0.0156 | 0.0179 | 0.0243 |
| G2, 4 fundamental hypers | 12 | disabled | 0.0291 | 0.0194 | 0.0053 | 0.0000 | 0.0000 | 0.0247 | 0.0033 |
| G2, 4 fundamental hypers | 12 | miss | 0.0496 | 0.0197 | 0.0053 | 0.0008 | 0.0000 | 0.0386 | 0.0034 |
| G2, 4 fundamental hypers | 12 | hit | 0.0073 | 0.0000 | 0.0000 | 0.0000 | 0.0012 | 0.0029 | 0.0034 |
| G2, 4 fundamental hypers | 18 | disabled | 0.4418 | 0.3326 | 0.0832 | 0.0000 | 0.0000 | 0.4145 | 0.0244 |
| G2, 4 fundamental hypers | 18 | miss | 0.4874 | 0.3479 | 0.0799 | 0.0080 | 0.0000 | 0.4525 | 0.0251 |
| G2, 4 fundamental hypers | 18 | hit | 0.0640 | 0.0000 | 0.0000 | 0.0000 | 0.0352 | 0.0371 | 0.0239 |
| SU(2) x SU(2), 2 bifundamental hypers | 12 | disabled | 0.1102 | 0.0822 | 0.0188 | 0.0000 | 0.0000 | 0.1009 | 0.0083 |
| SU(2) x SU(2), 2 bifundamental hypers | 12 | miss | 0.1317 | 0.0797 | 0.0192 | 0.0032 | 0.0000 | 0.1153 | 0.0084 |
| SU(2) x SU(2), 2 bifundamental hypers | 12 | hit | 0.0159 | 0.0000 | 0.0000 | 0.0000 | 0.0045 | 0.0063 | 0.0084 |
| SU(2) x SU(2), 2 bifundamental hypers | 18 | disabled | 2.7421 | 2.3173 | 0.3289 | 0.0000 | 0.0000 | 2.6462 | 0.0885 |
| SU(2) x SU(2), 2 bifundamental hypers | 18 | miss | 2.7843 | 2.2629 | 0.3313 | 0.0416 | 0.0000 | 2.6805 | 0.0910 |
| SU(2) x SU(2), 2 bifundamental hypers | 18 | hit | 0.3251 | 0.0000 | 0.0000 | 0.0000 | 0.2339 | 0.2366 | 0.0841 |
| SU(5), 1 symmetric + 1 antisymmetric hyper | 12 | disabled | 0.3665 | 0.2652 | 0.0499 | 0.0000 | 0.0000 | 0.3152 | 0.0497 |
| SU(5), 1 symmetric + 1 antisymmetric hyper | 12 | miss | 0.4153 | 0.2522 | 0.0506 | 0.0077 | 0.0000 | 0.3565 | 0.0500 |
| SU(5), 1 symmetric + 1 antisymmetric hyper | 12 | hit | 0.1136 | 0.0000 | 0.0000 | 0.0000 | 0.0352 | 0.0371 | 0.0747 |
| SU(5), 1 symmetric + 1 antisymmetric hyper | 18 | disabled | 13.7565 | 11.5183 | 1.3767 | 0.0000 | 0.0000 | 12.8822 | 0.9455 |
| SU(5), 1 symmetric + 1 antisymmetric hyper | 18 | miss | 14.1896 | 11.6151 | 1.4106 | 0.2430 | 0.0000 | 13.3092 | 0.8670 |
| SU(5), 1 symmetric + 1 antisymmetric hyper | 18 | hit | 1.8771 | 0.0000 | 0.0000 | 0.0000 | 1.0136 | 1.0188 | 0.8405 |

## Reproduce

From the project root:

```bash
DOT_SAGE=/tmp/codex-sage-cache PYTHONDONTWRITEBYTECODE=1 /home/subo-lee/miniconda3/envs/sage/bin/sage -python -B output/benchmarks/form_expansion_theories/benchmark.py
```

The benchmark keeps its prefilled databases under `cache/`; the project-root caches are only read to seed copies. Exact inputs, FORM programs, final index coefficients, cache row counts, prefilling durations, individual trials and environment details are in [results.json](results.json).
