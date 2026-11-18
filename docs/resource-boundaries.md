# Downloaded resources and publication boundaries

Keep official rules in `private-resources/rules-manuals/YEAR/`. Keep other downloaded third-party materials (scoresheets, checklists, tests, presentations, saved pages) under `private-resources/YEAR/EVENT/`. That directory is ignored in Git and excluded from container staging and distribution packaging.

Source registries should record links, dates, licenses and concise original notes, not copied manuals. Original author-created lessons, diagrams and code remain in source; retained vector/PDF art is not blanket-ignored. Generated final reader PDFs/web are ignored build outputs, deployed to Pages as artifacts rather than committed to a second repository. Authored Thermodynamics interactive inputs live in source/interactives/runtime; Solar reader metadata lives in source/reader-metadata. Generated web files are not authoring inputs.

A .gitignore is not a rights license, does not remove already-tracked files and does not purge past commits. The `soso` repository contains source, while GitHub Actions builds and deploys the public site. Before pushing, review tracked files and retained Git history for restricted material. Do not publish downloaded SO material or assume that availability for free permits redistribution. The official policy is https://www.soinc.org/copyrights-media-and-use . Independently authored summaries, branding and every third-party asset still need an appropriate publication review; these exclusions are a preventive boundary, not a legal clearance.

Prior local ZIPs are preserved as historical snapshots and may contain restricted downloads. Do not distribute those archives. Regenerate current bundles with the updated packager. No tracked/history removal or publication is authorized by this organization step.

Shell entry points `build-container/build-image.sh` and `build-container/run.sh` are executable. Transfer workflows must preserve intended executable modes as well as file contents; Python modules are invoked through Python and need not be executable.
