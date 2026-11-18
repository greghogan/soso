# Document builder

The root `./build.sh` command builds the toolchain image, compiles the PDFs and interactive readers, and exports the public site. GitHub Actions uses the same command. Docker is the only host dependency.

The image uses the official Python/Debian base plus XeLaTeX, fonts, librsvg and pinned Python packages installed by uv. The uv binary is pinned to an official multi-architecture image digest; the existing requirements file remains the single dependency list. uv installs into the isolated image, so no host uv installation or extra virtual environment is required. Docker chooses the native architecture: arm64 on Apple Silicon, amd64 on typical Intel/AMD hosts. Unchanged layers are cached. The recipe deliberately favors ordinary packages over a custom minimal toolchain.

## Individual steps

From the repository root:

```sh
./build-container/build-image.sh
./build-container/run.sh "$PWD" ../soso-candidates-new
```

Both default to `soso-builder:development`. `run.sh` accepts a third argument to use a specific image ID and requires a new output directory. The root `./build.sh` safely manages repeat builds in its own output directory, preserving the last successful output if a build fails. Compilation mounts the source read-only and runs offline, with temporary writable storage. Allow at least 2 GB for temporary build files, plus image storage.

`export_site.py` exports only reader-facing files selected by the build report: PDFs, HTML, supporting assets and license notices. Rules manuals, downloaded resources, source, logs and Git history are not exported. Root `build.sh` runs the exporter inside Docker, so host Python is not needed.

## What is rebuilt

`manifests/events.json` selects the event renderers. The runner builds PDFs/readers, the exam reference, catalogs and navigation; it also checks local dependencies and records logs, page counts, hashes and installed package versions under `candidates/`.

This rebuilds documents from retained assets, not every asset from scratch. Keep canonical lessons, authored interactive runtime files, reader metadata, fonts, artwork and diagram masters. Compilation is not a substitute for scientific, rules, copyright or every-page visual review.

## Repeatability

Default builds use the moving `python:3.12-slim-trixie` tag and current Debian packages. They are not byte-reproducible: tooling, fonts and PDF metadata can change. Record and reuse the printed immutable image ID when comparing a release.

For a toolchain rebuild with fixed base inputs, resolve a real base-image digest and Debian snapshot timestamp, then run:

```sh
BASE_IMAGE='python:3.12-slim-trixie@sha256:ACTUAL_64_HEX_DIGEST' \
DEBIAN_SNAPSHOT='YYYYMMDDTHHMMSSZ' IMAGE_TAG='soso-builder:reviewed' \
./build-container/build-image.sh locked
```

The wrapper rejects these literal placeholders. This fixes the base and Debian repository date, but Python wheel hashes are not locked. Do not claim a byte-identical rebuild; compare rendered pages and text as well as hashes. Refresh dependencies deliberately and review the resulting documents.

## Publication images

The site exporter keeps canonical source images unchanged. Opaque photo/art assets explicitly selected by each event’s `photo_asset_globs` in `manifests/events.json` use WebP quality 90, method 6, only when smaller; PNG and transparent assets stay lossless. A 1600-pixel long-edge target serves typical high-density reading views; resizing must save at least 10%. PDF photographic raster streams are identified by decoded-pixel hashes of those source assets in the private build report. They use JPEG quality 90 with 4:4:4 color sampling; existing JPEGs remain unchanged unless oversampled. Selected photo/art images above 360 ppi can be resized to 300 ppi at their largest placement. Text, vectors, transparency and unselected raster art retain their original resolution and lossless encoding. PDF color-space references are retained; unusual sample depths and decode maps are left untouched. PDF derivatives come from the full-quality candidate, never the lossy web derivative. Both lossy compression and resizing discard detail: review identification features and enlargement-critical images at intended sizes. Published manifests describe resulting files, not source masters.

The image/PDF regression fixtures run in the builder: `docker run --rm --entrypoint python -v "$PWD:/work:ro" soso-builder:development /work/build-container/check_asset_export.py`.

Canonical photographic raster masters use lossless JPEG XL. `manifests/raster-masters.json` retains original hashes and decoded-pixel hashes; existing JPEGs are reversibly archived. `djxl` decodes only into disposable build caches and verifies the retained identities. Artwork uses distance 0 / effort 8; JPEG reconstruction uses effort 7. Web/PDF derivatives are generated independently. SVG and technical PNG sources remain unchanged.
