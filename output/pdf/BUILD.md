# PDF sources and rebuilding

Both final PDFs have retained LaTeX sources in this directory:

- `n2_implementation_reference_summary.tex` builds the package reference here.
- `n2_theory_index_Mathematical_Background.tex` builds the index algorithm guide;
  its canonical PDF is `../../index/n2_theory_index_Mathematical_Background.pdf`.

The index guide includes `source_assets/n2_background_preserved_pages_2_to_4.pdf`
to retain unrevised content from the original document exactly. Original page 2
has one revised sentence describing SQLite storage; pages 3-4 are unchanged.
Keep this asset with the TeX source. The remaining pages are authored in LaTeX.

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

The 10 September 2026 revision changes cache/projection sections and relevant
metadata, API mappings and validation. Unrevised equations retain their original
numbering. In the index guide, new projection equations use labels (28a)-(28d)
so the original equations (1)-(30) remain stable. Other package chapters in the
consolidated reference retain their earlier dated snapshot.
