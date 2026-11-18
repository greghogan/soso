#!/bin/sh
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
mode=${1:-development}
base=${BASE_IMAGE:-python:3.12-slim-trixie}
snapshot=${DEBIAN_SNAPSHOT:-}
tag=${IMAGE_TAG:-soso-builder:development}
case "$mode" in
  development) ;;
  locked)
    case "$base" in *@sha256:*) ;; *) echo 'Locked builds require BASE_IMAGE with an exact sha256 digest.' >&2; exit 2;; esac
    printf '%s\n' "$base" | grep -Eq '@sha256:[0-9a-f]{64}$' || exit 2
    printf '%s\n' "$snapshot" | grep -Eq '^[0-9]{8}T[0-9]{6}Z$' || { echo 'Locked builds require DEBIAN_SNAPSHOT=YYYYMMDDTHHMMSSZ.' >&2; exit 2; }
    ;;
  *) echo 'Usage: build-image.sh [development|locked]' >&2; exit 2;;
esac
command -v docker >/dev/null || { echo 'Docker is not available; nothing was installed.' >&2; exit 1; }
docker build --build-arg "BASE_IMAGE=$base" --build-arg "DEBIAN_SNAPSHOT=$snapshot" --tag "$tag" "$here"
printf '\nBuilt image identity (record this with the release):\n'
docker image inspect --format '{{.Id}}' "$tag"
