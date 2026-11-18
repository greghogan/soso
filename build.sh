#!/bin/sh
# Build all PDFs/readers and export the Pages artifact using Docker only.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
output=${1:-"$here/build"}
if [ "$#" -gt 1 ]; then
  echo 'Usage: ./build.sh [BUILD_DIRECTORY] (default: ./build)' >&2
  exit 2
fi
# Only directories created by this wrapper may be reused. Never adopt or delete
# an arbitrary existing directory (including outputs from older wrapper versions).
marker='.soso-build-output'
identity='SOSO generated build output v1'
if [ -L "$output" ]; then
  echo "Refusing symlink build directory: $output" >&2
  exit 2
fi
if [ -e "$output" ]; then
  if [ ! -d "$output" ] || [ -L "$output/$marker" ] || \
     [ ! -f "$output/$marker" ] || [ "$(cat "$output/$marker")" != "$identity" ]; then
    echo "Refusing unmarked build directory: $output" >&2
    echo 'Choose a new directory, or move the old generated build aside once.' >&2
    exit 2
  fi
else
  mkdir -p -- "$output"
  printf '%s\n' "$identity" > "$output/$marker"
fi
output=$(CDPATH= cd -- "$output" && pwd)
# Serialize builds targeting the same output; never replace another live build.
if ! mkdir "$output/.lock" 2>/dev/null; then
  echo "Build already running (or stale lock): $output/.lock" >&2
  exit 2
fi
trap 'rmdir "$output/.lock"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
for name in .next .previous candidates site site-export.json; do
  if [ -L "$output/$name" ]; then
    echo "Refusing symlink inside build output: $output/$name" >&2
    exit 2
  fi
done
if [ -e "$output/.previous" ]; then
  echo "Previous output promotion was interrupted; recover $output/.previous before rebuilding." >&2
  exit 2
fi
# Failed attempts retain their diagnostics here until the next attempt.
rm -rf -- "$output/.next"
mkdir "$output/.next"
stage="$output/.next"
image=${IMAGE_TAG:-soso-builder:development}
"$here/build-container/build-image.sh" development
"$here/build-container/run.sh" "$here" "$stage/candidates" "$image"
docker run --rm --network none --read-only \
  --user "$(id -u):$(id -g)" --cap-drop ALL --security-opt no-new-privileges \
  --mount "type=bind,src=$here/build-container,dst=/scripts,readonly" \
  --mount "type=bind,src=$stage,dst=/output" \
  --entrypoint python "$image" /scripts/export_site.py /output/candidates /output/site
# Compilation/export must succeed before replacing the last good outputs.
# Keep old outputs until promotion finishes, then discard this generated backup.
mkdir "$output/.previous"
for name in candidates site site-export.json; do
  if [ -e "$output/$name" ]; then mv -- "$output/$name" "$output/.previous/$name"; fi
  mv -- "$stage/$name" "$output/$name"
done
rmdir "$stage"
rm -rf -- "$output/.previous"
printf '\nPages site: %s/site\n' "$output"
