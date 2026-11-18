# SOSO

Editable sources and build tools for the SOSO Study Omnibrary. One repository builds the PDFs, interactive guides and GitHub Pages website; generated documents are not committed.

## Authoring

`manifests/events.json` selects event/year renderers and outputs; see `docs/series-structure-and-workflow.md` to add an event.

- `events/<event>/2027/source/`: canonical lessons, citations, diagrams/renderer code and event metadata.
- `events/<event>/2027/assets/`: retained source artwork and vector masters. A PDF here can be a diagram input, not a finished manual.
- Thermodynamics and Water Quality interactive HTML/JS/CSS: `source/interactives/runtime/`; Solar reader metadata: `source/reader-metadata/`.
- `shared/`: notation, print styles and common renderers. `scripts/`: contributor commands. `soso/`: asset and site implementation. `tests/`: tooling checks.
- `manifests/`: event registry, asset hashes, and provenance.
- `docs/manual-standard.md`: authoring and reader conventions. `manifests/rights-inventory.json`: item-level publication review status.

Edit source, never generated `web/` or finished guide PDFs. Historical bootstrap scripts under `source/authoring/` are retained reference, not the current regeneration entry point.

## Build and publish

From this repository, with uv installed and Docker running:

```sh
./scripts/asset_fetch.py  # First checkout, or when the image manifest changes
./build.sh
```

Asset fetch uses the local cache first and verifies every downloaded original.
See [asset storage](docs/asset-storage.md) for backup setup and public-only fetch. For one event’s web preview use `./scripts/build_web.py EVENT`; see [offline distributions](docs/standalone.md) for standalone HTML and ZIPs.

Independent events build in parallel with at most three workers (also capped by available CPUs and container memory, budgeting 1 GiB per worker). Each event’s steps remain sequential. Use `SOSO_BUILD_JOBS=1 ./build.sh` for a serial build, or set another positive worker limit. Command timings are recorded in `build/candidates/build-report.json`.

Open `build/site/index.html` to preview the website. `build/candidates/` holds the generated documents and build logs. Docker chooses the host architecture; PDF compilation needs no host TeX or SVG application. Run `./build.sh` again to rebuild. It preserves the last successful output until the new build succeeds; a failed attempt leaves diagnostics in `build/.next/`. Existing build directories from older versions must be moved aside once before the new script can manage them. Source and local reference folders are never overwritten. Direct guide and web builds use `build/direct/`; the standalone and ZIP tools default to `build/standalone/` and `build/distributions/`. Authored content and retained source assets stay in `events/`.

GitHub Actions runs source and interactive tests on pull requests without private storage access. Pushes to `main` and manual runs on `main` build and deploy `build/site/` to GitHub Pages. These release builds read missing originals only from configured private S3 storage. See [asset storage](docs/asset-storage.md) for the optional pre-push check. In repository **Settings → Pages**, select **GitHub Actions** as the source. For `greghogan/soso`, the website is `https://greghogan.github.io/soso/`. No second repository or generated-content branch is needed. Review scientific claims and changed layouts before merging; compilation does not perform that review.

The build container uses ordinary official Python/Debian packages, not a custom published builder image. Build-time downloads need network access; document compilation and export run offline. Docker caches unchanged toolchain layers. See `build-container/README.md` for individual build steps and reproducibility limits.

## Checks

```sh
./test.sh                 # source and interactive tests
./test.sh build/candidates # also check the generated catalog and offline bundles
```

Tests require Python 3, Node.js, and uv (which manages the storage SDK test environment); once the image cache is populated, the document build itself requires only Docker. GitHub Actions runs the tests and retains build diagnostics separately from the published site. Browser interactions and scientific/copyright review are separate from automated checks.

## Licensing and publication

[LICENSE.md](LICENSE.md) applies Apache-2.0 to original code and CC BY 4.0 to original educational content/artwork, with third-party/public-domain/AI-provenance exceptions. [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt) retains upstream font terms.

Asset provenance and reuse exceptions are recorded in `manifests/rights-inventory.json`. The three raster art-direction references have recovered identities and owner-attested ChatGPT origin; upstream generation inputs remain unverified (see `docs/reference-provenance-2026-11-16.md`). Do not treat our content license as a license to third-party material.

Keep official rules in `private-resources/rules-manuals/` and other downloaded research references under `private-resources/`. Neither is a build input. Downloaded image originals are managed separately by the [asset tools](docs/asset-storage.md) under the ignored root `assets/` directory.
