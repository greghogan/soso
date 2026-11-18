#!/bin/sh
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
source=${1:-$(dirname "$here")}
output=${2:?Usage: run.sh SOURCE_DIRECTORY NEW_OUTPUT_DIRECTORY [IMAGE]}
image=${3:-soso-builder:development}
source=$(CDPATH= cd -- "$source" && pwd)
if [ -e "$output" ]; then echo 'Output must be a new directory; approved files will not be replaced.' >&2; exit 2; fi
command -v docker >/dev/null || { echo 'Docker is not available; nothing was installed.' >&2; exit 1; }
mkdir -p -- "$output"
output=$(CDPATH= cd -- "$output" && pwd)
docker run --rm --network none --read-only \
  --user "$(id -u):$(id -g)" --cap-drop ALL --security-opt no-new-privileges \
  --tmpfs /tmp:rw,nosuid,nodev,size=512m --tmpfs /work:rw,nosuid,nodev,size=2g,mode=1777 \
  --mount "type=bind,src=$source,dst=/source,readonly" \
  --mount "type=bind,src=$output,dst=/output" \
  --env "SOSO_BUILD_JOBS=${SOSO_BUILD_JOBS:-3}" \
  --env "MANUAL_BUILDER_IMAGE=$image" "$image"
