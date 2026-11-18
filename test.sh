#!/bin/sh
# Existing source/model regression tests; optionally check a generated candidate tree.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ "$#" -gt 1 ]; then
  echo 'Usage: ./test.sh [BUILD_CANDIDATES_DIRECTORY]' >&2
  exit 2
fi
cd "$here"
command -v python3 >/dev/null || { echo 'Tests require Python 3.' >&2; exit 1; }
command -v uv >/dev/null || { echo 'Storage tests require uv.' >&2; exit 1; }
command -v node >/dev/null || { echo 'Tests require Node.js.' >&2; exit 1; }
unset SO_PROJECT_ROOT
python3 build-container/test_source.py
python3 -m unittest discover -s build-container -p 'test_*.py'
python3 -m unittest tests.test_event_registry tests.test_resource_boundaries tests.test_water_quality tests.test_build_paths
uv run --locked --group test python -m unittest tests.test_asset_prompts tests.test_asset_pre_push tests.test_asset_sync tests.test_asset_fetch tests.test_asset_storage tests.test_asset_setup tests.test_asset_diagnostic_git tests.test_asset_diagnostic_run tests.test_asset_iam_setup tests.test_asset_setup_dispatch tests.test_asset_setup_gcs tests.test_asset_setup_azure tests.test_asset_setup_s3compatible tests.test_asset_aws tests.test_asset_integrity tests.test_asset_gcs tests.test_asset_azure
node events/thermodynamics-b/2027/source/interactives/test-models.cjs
node tests/reader_state_test.cjs soso/site/standalone
node events/water-quality-b/2027/source/interactives/test-practice.cjs
if [ "$#" -eq 1 ]; then
  candidates=$(CDPATH= cd -- "$1" && pwd)
  if [ ! -f "$candidates/build-report.json" ]; then
    echo 'Expected a completed build candidates directory containing build-report.json.' >&2
    exit 2
  fi
  SO_PROJECT_ROOT="$candidates" python3 -m unittest tests.test_catalog tests.test_standalone
fi
