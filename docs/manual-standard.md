# Manual production standard

Applies to all SOSO study/build manuals. The exam reference is a separate retrieval aid, with its own page limits; do not silently restyle or expand it.

## Authoring contract

1. Keep scientific content in canonical lesson JSON; render print and web from that content. Retain stable lesson and answer IDs.
2. Each lesson needs a clear question or purpose, necessary prerequisite explanation, a concise mechanism or evidence account, and an independent question with explanatory feedback. Include worked examples where a procedure or quantitative relationship is being taught.
3. Prefer this adaptable sequence: purpose → explanation with relevant visual → modeled reasoning → independent attempt → separate explanatory answer. Revisit prior ideas through mixed questions later. Do not mechanically add every component to every lesson.
4. Questions should include recall, explanation, prediction, evidence interpretation and transfer, not only recognition. A wrong-answer explanation should address the likely misconception. Do not infer mastery from reading or a correct guess.
5. Scientific claims and uncertainty belong in captions when they change interpretation. Omit obvious disclaimers such as “not a photograph” or “not a map” for plainly schematic art. Retain scale, orientation, alternative-model and unmeasured-feature warnings when scientifically useful.
6. Every visual must have a teaching purpose. Insert a shared comparison figure once and refer back by stable link and printed page number. Repeat only when the second rendering adds a new annotation, scale, task or comparison, and document why.
7. Author review identifies rules coverage and sources. Read the actual current-year manual, the event’s complete official clarification entries and official corrections; a landing page or empty search result is not enough. Record checked dates and distinguish mandatory requirements, supervisor discretion, recommendations and our design choices. Search all active lesson, answer and interactive copies for superseded interpretations before release. Do not silently alter rules scope, safety constraints, or uncertain findings for cosmetic reasons.

## Visual language

Use shared/guide-style.tex for print typography and semantic cues. Keep a small, labeled, monochrome-safe cue set: lightbulb for Think it through (reasoning), connected steps for Worked example (modeled steps), pencil for Try it (independent application), and open book with a return arrow for Review (retrieval across earlier material). Use only where the content performs that function. The canonical geometry in shared/learning-icons/generate.py generates genuine SVG artwork for web and matching native vector paths for print; do not substitute text characters or unrelated icon fonts. Retain the words, and inspect icons at their actual reading size. Do not decorate every paragraph.

Use a serif reading face and sans-serif navigation/captions. Body prose, narrow cells and captions are left-aligned with a ragged right edge. Avoid forced justification, stretched word spacing and discretionary splits like “s-pace.” Tables are for genuine comparisons or recording data, not narrative cards. A worksheet must be usable: put constant setup conditions in a form header, use a manageable set of labeled/unit-bearing columns for trial data, and allow real writing space. Decision logs need distinct before-test, after-test and decision areas. Pipes in prose and tiny inline underscores are not printable worksheets.

Generated artwork should match the polish of the strongest existing guide: coherent lighting and depth, credible anatomy and environmental relationships, purposeful composition, and no garbled labels or distracting empty framing. Inspect the actual pixels at source and final printed size. Regenerate weak artwork rather than disguising flaws with layout. Use generated scenes to explain context and mechanisms, never as evidence for organism identification. Recognition lessons need correctly identified, individually credited real photographs; where an event category spans species or appearances, show meaningful variation and explain which features persist and where a photograph cannot support certainty.

Follow [image-selection.md](image-selection.md) for comparative sourcing, diagnostic selection, provenance and final-size review of identification photographs.

Cover text may sit directly on suitably dark image regions. Verify contrast at actual size and in grayscale; do not restore opaque panels by default. Reposition or simplify text before adding effects. Do not obscure scientifically important imagery. Do not stretch artwork differently in its two dimensions. Preserve source pixels. Decorative empty framing may be cropped through explicit reusable viewport metadata; inspect the full source and the cropped result so no explanatory feature is lost.

Keep headings with enough following content to establish the idea. Keep a question with its prompt and a figure with its caption. Avoid oversized keep-together blocks that leave excessive empty pages. Figure labels must be comfortably readable at 100% print size. Prefer measured block sizes or short heading-and-first-paragraph reservations over large fixed keep-together allowances. Audit unusually large empty page tails and explain intentional exceptions; never solve excess whitespace by shrinking readable type or cramming unrelated topics. Contact sheets locate outliers, but actual-size page inspection decides whether a layout works.

Scientific typography is semantic: chemistry indices must visibly sit below the baseline and powers above it, using explicit subscript/superscript layout rather than relying on a font’s Unicode appearance. Preserve element capitalization (CO is not Co). Validate both rendered appearance and extracted/searchable meaning; correct pasted Unicode alone does not establish correct visual positioning. Display multi-term scoring equations and substantial worked calculations on separate lines; use true fractions, absolute-value delimiters and named subscripts consistently. Do not invent missing rule definitions or denominator-zero behavior while reformatting.

Answers come after independent attempts. Place “Return to the lesson” after the explanation, with a functioning link and printed page reference. Keep navigation visually subordinate to content. Number each practice question and each answer separately using structural list items, not a run-on paragraph containing multiple numbers. Table-of-contents entries must distinguish destinations with repeated chapter names. Where a lesson intentionally continues after a page break, retain a useful continuation heading or running context rather than beginning with an unexplained fragment.

## Reader orientation

Every independently distributed guide, exam reference and web page must identify SOSO as independent and not affiliated with or endorsed by Science Olympiad. Use the shared PDF credit and web footer; do not repeat a disclaimer at every mention or imply ownership of the trademark. Retain licensing exceptions and asset-specific credits.

Include the shared “How to learn with this guide” introduction, explaining cue meanings, attempt-before-answer, self-explanation, later retrieval and mixed review. A study manual teaches; the exam reference helps retrieve already-understood material. Do not present either as a substitute for current official rules.

Follow [provenance.md](provenance.md) for canonical source records, generated attributions and text citations.

## Required production checks

- Validate canonical IDs, questions, answer anchors, sources and figure paths.
- Compile every changed PDF twice or until cross-references stabilize.
- Confirm embedded fonts, intended page size, link targets, no missing glyphs, no undefined references and no overflowing text.
- Render every page. Review covers, narrow tables, side-by-side explanations, page breaks, captions, questions, answer links, figure reuse and blank-space outliers. Review each page at readable size; contact sheets only locate patterns. Check graph-label collisions, equation baselines, continuation context and whether a student can actually write in worksheets.
- After implementation is frozen, obtain an independent review of all revised documents. Log findings and re-review changed pages after corrections; do not substitute the implementer’s compile check for that review.
- Check grayscale legibility and print at 100%; never rely on hue alone.
- Preserve original PDFs until the replacement passes. Record page counts, tested outputs and remaining limitations in a dated review.
- Regenerate affected web output and distribution bundles, then refresh the manifest and run project tests.
- Before claiming improved learning outcomes, test representative lessons with students. Record confusing questions, explanation quality and delayed recall. These design principles support learning; this manual's effectiveness is not experimentally established.

Evidence informing the learning sequence: Institute of Education Sciences, Organizing Instruction and Study to Improve Student Learning, https://ies.ed.gov/ncee/WWC/PracticeGuide/1 .

## Repository and publication boundary
Canonical content, editable assets, build tools and standards belong in the single `soso` repository. Generated static documents and reader-facing web outputs are build artifacts, not committed source. GitHub Actions deploys the generated site to Pages. Keep downloaded rules and other private references ignored and excluded from the build. Preserve prior history and backups; repository organization does not authorize their deletion. See series-structure-and-workflow.md.

## Canonical structured components
Thermodynamics worksheet records use `kind`, stable `id`, `title`, `purpose`, and `sections`. A section is `fields` or `table`; a field has a label and writing-line count, while a table specifies columns, proportional widths, row count and row height. Keep trial setup and decision logs reusable and linked from the lesson. The print renderer and accessible web output must represent the same fields.

Authored `display_equations` provide panel placement plus TeX and MathML representations of the same formula. Shared `math_notation.py` owns boundary-aware index notation; figures use explicit vertical positioning from that registry. Test both appearance and meaning. Practice questions and answers are arrays of distinct items. Do not reintroduce numeral-delimited prose.

Covers share a hierarchy (event, year, manual kind and short learning purpose) without requiring identical artwork. Solar System uses atmospheric art; Thermodynamics study uses a conceptual calorimetry cutaway, while its build cover and exact teaching diagrams retain vector apparatus/process art. Cover apparatus must not imply a permitted competition design unless checked against that event’s rules. Cover treatment must not hide artwork or compete with the title.
