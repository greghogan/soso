# Exam reference source

`content.json` is the canonical four-page content. Edit prose and scientific values there, and typography in `export_tex.py`. The generated LaTeX and optional Markdown view live in the build tree, not next to their source.

`export_tex.py` preserves every canonical text field and ten reviewed mathematical display groups. An equation-source checksum prevents unnoticed drift. `status-sources.html` preserves the exact dated citation text formerly read indirectly from an older renderer.

From the project root:

```sh
python3 events/solar-system-b/2027/source/exam-reference/build.py
```

The command exports a candidate TeX file, runs XeLaTeX twice, rejects overflow/missing-glyph/font warnings, and validates four US Letter pages, 154 canonical text strings, nine worlds, three systems, sixteen missions, and three citation links. It writes `build/direct/events/solar-system-b/2027/build/exam-reference/exam-reference.pdf`, TeX, logs, and a validation report. The approved release is not modified.

Dependencies: Python with `pypdf` (pinned in the project requirements), plus a TeX distribution supplying `xelatex`, Latin Modern Sans, `fontspec`, `fix-cm`, `amsmath`, `amssymb`, `array`, `tabularx`, `geometry`, `fancyhdr`, and `hyperref`. No TeX distribution was installed during cleanup. If XeLaTeX is absent, the build exits clearly before writing candidates.

To validate the last candidate PDF and emitted TeX without XeLaTeX, run `python3 events/solar-system-b/2027/source/exam-reference/validate.py` from the project root. Its report goes next to the candidate. To test the exporter alone, run `export_tex.py`; its default output is under `build/`. Run `export_markdown.py` for a human-readable export next to the generated TeX.
