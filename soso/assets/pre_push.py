"""Verify the exact asset manifest being pushed to origin/main."""
import subprocess
import sys

from . import asset_storage, asset_sync


def main(commit):
    try:
        manifest = subprocess.check_output(
            ['git', 'show', f'{commit}:manifests/external-assets.json'], text=True,
        )
        assets = asset_sync.parse_records(manifest)
        backup = asset_sync.configured_destination()
        if not backup:
            raise ValueError('No storage configured. Run ./scripts/asset_setup.py first.')
        print(f'Checking assets for origin/main ({commit[:12]}) in {backup}.', flush=True)
        present = asset_sync.list_manifest_objects(asset_storage.parse(backup), assets)
        if asset_sync.verify_assets(assets, asset_sync.DEFAULT_CACHE, backup, present=present):
            return 0
        print('Push blocked: originals are missing. Run ./scripts/asset_sync.py for the manifest being pushed, then retry.',
              file=sys.stderr)
    except (subprocess.CalledProcessError, ValueError, KeyError, TypeError, RuntimeError, OSError) as exc:
        print(f'Push blocked: could not verify release assets: {exc}', file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
