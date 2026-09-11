# PDF sources and rebuilding

The 11 September 2026 project rename updates both PDFs to **N2SCFTDB**,
including titles, running headers and PDF metadata. Mathematical content and
dated benchmark/test evidence remain unchanged. The sources rebuild from any
checkout directory, including `/home/subo-lee/PycharmProjects/N2SCFTDB`.

Both final PDFs have retained LaTeX sources in this directory:

- `n2_implementation_reference_summary.tex` builds the package reference here.
- `n2_theory_index_Mathematical_Background.tex` builds the index algorithm guide;
  its canonical PDF is `../../index/n2_theory_index_Mathematical_Background.pdf`.

The index guide includes `source_assets/n2_background_preserved_pages_2_to_4.pdf`
to retain unrevised content from the original document exactly. Original page 2
has one revised sentence describing SQLite storage; pages 3-4 are unchanged.
Keep this asset with the TeX source. The remaining pages are authored in LaTeX.
Both documents also include `cache_session_algorithms.tex` and
`cache_session_validation.tex`; retain these shared inputs when transferring
the sources. They document the same implementation and benchmark evidence
without duplicating the authored text.

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

The latest 10 September 2026 revision describes source commit `04bbe21`:

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
A32 profiles are explicitly dated as preceding FORM expansion caching. Other
package chapters in the consolidated reference retain their earlier snapshot.

Validation during this update uses the real Sage/FORM/LiE test backends; live
MySQL tests are disabled. No application source or production database is
changed. The benchmark numbers are retained measurements, not rerun timings.

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

Verified outputs for this revision: 34-page implementation reference and
20-page index guide. Both were rendered and visually checked; equation-tag
sequences match the prior PDFs, with no unresolved references or overfull boxes.
The full test rerun was 209 tests in 19.658 seconds: 207 passed, 2 MySQL skips.
