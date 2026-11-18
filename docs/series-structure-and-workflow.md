# Adding an event

`manifests/events.json` is the build registry. The `soso` repository contains editable lessons, assets and build tools; generated pages and PDFs are ignored build outputs deployed to GitHub Pages. Downloaded rules stay in ignored local folders.

## Registry and renderer contract

For each event/year, add one entry with `slug`, `year`, display `name`, `division`, `build` commands, a `web_build` command, `required_inputs`, `site_assets`, and optional `promote` mappings. Paths are relative to `events/<slug>/<year>/`; a command beginning `@root/` selects a shared script. Commands run with Python, the project as working directory, and `SOSO_EVENT_DIR` pointing to the selected event directory. Do not put shell commands in the registry.

Declare reader links in `documents`: `study` and `build` can each have a `pdf` and/or `interactive` path; `exam` is PDF-only. The build/export PDF list is derived from these paths. Omit inapplicable editions; the catalog keeps their positions grayed out. Optional `models` entries supply `path`, `title`, and `description` for the event-page model cards. Set `web_landing: true` only when `web/index.html` should be a generated event hub rather than an authored reader.

Keep event-level `reference_constraints` separate from `documents`: a permitted reference can still be unwritten. Record `status` (`allowed`, `not_allowed`, `not_applicable`, or `unspecified`), and for allowed paper references the `allocation` (`team` or `participant`), `sheet_limit`, `sides_per_sheet`, `paper_size`, and `rule_source`. An explicit null sheet limit means unlimited; missing metadata means unknown, not unlimited. PDF pages are sheet limit × usable sides, per declared allocation. A participant allowance is not automatically multiplied by team size. For finite allowances, produce a useful reference matching the allowed page count; for unlimited paper, choose length editorially. Keep binding/annotation restrictions in `notes`. Current metadata supports paper; verify a new format before extending it. Solar's PDF validator reads this allowance from the registry rather than hard-coding four pages.

The catalog and event pages are generated from this entry, not hand-edited. Generated `catalog-data.json` carries only public display/link metadata into the generated site; do not edit it there.

A renderer reads authored files under its event directory and emits the declared PDFs and a self-contained `web/` reader with an `index.html`. `promote` copies a newly generated candidate to its declared public filename. `site_assets` lists any additional local assets used outside `web/`. The container builds every registered entry and exports only the declared outputs, reader files, catalog and license notices. The web-only command is `python3 scripts/build_web.py EVENT --year YEAR`. It writes a preview tree and catalog under `build/direct/`; direct event renderers also write under `build/direct/events/<slug>/<year>/`. The full Docker build uses an isolated staging tree and leaves source directories untouched.

Keep reproducible diagram and reference generators under `source/`. Both print and web builds must regenerate what they consume from those sources. Write rendered vectors, previews, generated TeX or Markdown, and QA reports under `build/`, not a tracked event folder. Keep original artwork and approved masters under `assets/` only when the build cannot reproduce them.


The Solar and structured-lesson renderer families use different content schemas. Water Quality reuses the structured lesson renderer through `source/guide-config.json`: event identity, guide filenames, cover artwork and optional interactive pages are data rather than copied renderer code. Its organism atlas is canonical `source/organisms.json`, with item-level image credits retained in captions and provenance. The registry removes event/year selection from orchestration; it does not make existing science content or event-specific models generic. Reuse shared typography, notation, learning cues and worksheet components. A new event may supply a small adapter instead of copying an entire renderer. Do not simply copy a year's content and change its metadata: rules, citations and claims need review.

## Onboarding checklist

1. Confirm current official rules, corrections, division/year and distribution rights; retain third-party resources only in ignored local folders.
2. Map required topics to learning goals and the study/build/reference outputs that apply.
3. Write canonical lesson data, stable IDs, answers and citations; design figures around a learning purpose. Follow `manual-standard.md`.
4. Add the registry entry and build a representative lesson through PDF and web before expanding the manuscript.
5. Run source, build, link and packaging checks. Inspect every PDF page and test reader controls, offline behavior, mobile layout and print usability.
6. Run `./build.sh` to build candidate PDFs and export the site under ignored `build/` directories. Review before publication. GitHub Actions builds and deploys the exported site, not the source tree. Do not publish private resources, temporary reports or preview archives.

Keep only current, useful authoring documentation. Historical review logs and transfer backups belong outside the repository. A successful build is not scientific, visual or rights approval.
