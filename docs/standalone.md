# Optional offline distributions

Git is the editable source of truth. These tools package generated reader files only; they never create an editable-source ZIP or scan the working tree for source files.

First build from the repository root:

```sh
./scripts/asset_fetch.py
./build.sh
```

Both commands below use `build/candidates` by default. If you built elsewhere, pass `--project-root /path/to/build/candidates`. A clean source checkout is not a generated runtime tree.

## Single HTML file

HTML files default to `build/standalone/`:

```sh
./scripts/build_standalone.py solar-system-b
./scripts/build_standalone.py thermodynamics-b --include-pdfs
```

Use `--year YEAR` to select an edition (default 2027), choose a new path under `build/` or outside the repository with `--output` (its parent must already exist), or use `--stdout` to stream HTML bytes. Measurements and SHA-256 go to stderr. Existing outputs are never overwritten.

PDFs are excluded unless `--include-pdfs` is supplied. The single file embeds local pages, scripts, images and optional PDFs without resampling or lossy recompression. The reader needs JavaScript and modern support for Blob/object URLs, iframe.srcdoc, URLSearchParams and browser history. No server or network asset is required; external citations can optionally use the internet.

`soso/site/standalone/` contains the editable shell and route bridge. These tools produce distribution copies, not new authoring inputs. Identical inputs and tools produce identical bytes.

## Ordinary offline ZIPs

```sh
./scripts/package_distributions.py
```

This creates one ZIP per built event under `build/distributions/` (override with `--output-directory`), containing its reader pages, assets, declared PDFs and licensing notices. Extract a ZIP and open `index.html`. Each archive has a byte inventory. Existing archive files are never overwritten. Review the generated guides before sharing; packaging is not scientific or rights approval.

Editable source archives are no longer generated. Use the Git repository for source sharing and history; ignored manuals, downloaded resources, local settings and backups must remain private.

## Tests and limits

Python 3.9 or later is required. Node.js is needed for the JavaScript regression tests, not for packaging or reading.

```sh
./test.sh build/candidates
SO_PROJECT_ROOT=build/candidates python3 -m unittest tests.test_standalone
```

Tests check page text, IDs, disclosures, assets and local targets; deterministic bytes; default, explicit, and no-clobber output; PDF inclusion; and missing or network dependencies. JavaScript tests exercise models and reader state using DOM/history doubles. They do not replace actual browser, device, mobile-layout or offline-interaction testing.
