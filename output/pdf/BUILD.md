# PDF sources and rebuilding

The 12 September 2026 revision updates both N2SCFTDB PDFs for separate basic
property and index calculations, MySQL schema 7, the deferred index worker,
independent higher-order updates, legacy unknown precision, and partial retries.
The 238-test result is evidence recorded during implementation, not a test rerun
performed while rebuilding these documents. Existing equations and dated cache
benchmarks are retained. The earlier 11 September rename established the current
project branding and portable source paths.

Both final PDFs have retained LaTeX sources in this directory:

- `n2_implementation_reference_summary.tex` builds the package reference here.
- `n2_theory_index_Mathematical_Background.tex` builds the index algorithm guide;
  its canonical PDF is `../../index/n2_theory_index_Mathematical_Background.pdf`.

The index guide includes `source_assets/n2_background_preserved_pages_2_to_4.pdf`
to retain unrevised content from the original document exactly. Original page 2
has one revised sentence describing SQLite storage; pages 3-4 are unchanged.
Keep this asset with the TeX source. The remaining pages are authored in LaTeX.
Both documents also include `cache_session_algorithms.tex`,
`cache_session_validation.tex`, and `property_database_workflow.tex`; retain
all three shared inputs when transferring the sources. They keep shared algorithm, benchmark, and property/database descriptions
consistent without duplicating the authored text.

Run from `output/pdf` with a TeX Live installation that supplies the packages
listed in the preambles. Choose an existing temporary build directory. Two
passes resolve local equation, page and bibliography references; no BibTeX run
is needed because references are in `thebibliography`.

```bash
mkdir -p /tmp/sci-reference-build
pdflatex -interaction=nonstopmode -halt-on-error -output-directory /tmp/sci-reference-build n2_implementation_reference_summary.tex
pdflatex -interaction=nonstopmode -halt-on-error -output-directory /tmp/sci-reference-build n2_implementation_reference_summary.tex
pdflatex -interaction=nonstopmode -halt-on-error -output-directory /tmp/sci-reference-build n2_theory_index_Mathematical_Background.tex
pdflatex -interaction=nonstopmode -halt-on-error -output-directory /tmp/sci-reference-build n2_theory_index_Mathematical_Background.tex
```

Inspect logs for unresolved references and overfull boxes. Render the PDFs with
`pdftoppm -png` and review the pages before replacing the canonical outputs:

```bash
cp /tmp/sci-reference-build/n2_implementation_reference_summary.pdf ./n2_implementation_reference_summary.pdf
cp /tmp/sci-reference-build/n2_theory_index_Mathematical_Background.pdf ../../index/n2_theory_index_Mathematical_Background.pdf
```

The retained 10 September 2026 index/cache revision describes source commit `04bbe21`:

- Exact FORM-term serialization and SQLite lookup keyed by the full raw program.
- Per-thread/process connections, concurrent misses and cross-theory expansion reuse.
- Reuse of cached lower-order character factors and its measured limitations.
- `build_decomposition_cache`, Frobenius enumeration, process batches, order
  barriers, resume behavior, CLI examples and the `floor(N/2)` index cutoff.
- FORM cache I/O and nine-theory timings with character/singlet caches prefilled,
  planner comparisons and the 209-test validation snapshot (207 pass, 2 skips).

New displays in the shared inputs are unnumbered. Existing equation numbers
remain stable; the guide's projection equations retain labels (28a)-(28d).
The embedded source asset is unchanged by this revision. Older projection and
A32 profiles are explicitly dated as preceding FORM expansion caching. The property and database chapters now describe the 12 September workflow;
unrelated package chapters retain their earlier snapshots.

The database implementation was validated separately with 238 passing tests in
21.920 seconds, including actual Sage/FORM/LiE and a disposable MySQL 8.0.46
server. This documentation update verifies source contracts, two-pass builds,
PDF text and visual layout; it does not rerun that suite. No application source
or production database is changed. Benchmark numbers remain dated measurements.

For a reproducible layout review, render both staged outputs before copying:

```bash
mkdir -p /tmp/sci-reference-build/render
pdftoppm -r 110 -png /tmp/sci-reference-build/n2_implementation_reference_summary.pdf /tmp/sci-reference-build/render/reference
pdftoppm -r 110 -png /tmp/sci-reference-build/n2_theory_index_Mathematical_Background.pdf /tmp/sci-reference-build/render/background
```

Check every page, especially shared cache sections, tables and function maps.
The final LaTeX logs must have no unresolved citations/references or overfull
boxes. Build products and review PNGs belong in the temporary build directory,
not beside the tracked final PDFs.

Verified outputs for the 12 September revision: **39-page implementation
reference and 24-page index guide**. All pages were rendered and visually
reviewed, with the changed sections additionally checked at reading size.
There are no unresolved citations/references or overfull boxes. The reference
retains one pre-existing mild underfull-box diagnostic in the Coulomb API table;
it has no visible clipping or overlap. All 48 reference and 15 guide authored
equation/align environments remain verbatim, and embedded guide pages 2-4
retain their previous text. New cutoff-policy displays are unnumbered.

The prior 10 September validation was 209 tests in 19.658 seconds: 207 passed,
2 MySQL skips. It remains labeled as historical evidence in the shared cache
chapter rather than being presented as the current test result.
