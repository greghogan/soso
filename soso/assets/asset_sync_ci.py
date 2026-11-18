"""Read-only GitHub Actions backup verification using exact object keys."""
import os
import sys

from . import asset_storage, asset_sync


def main():
    try:
        if (os.environ.get('GITHUB_ACTIONS') != 'true'
                or os.environ.get('GITHUB_REF') != 'refs/heads/main'
                or os.environ.get('GITHUB_EVENT_NAME') != 'workflow_dispatch'):
            raise ValueError('CI backup verification is restricted to manual runs on main.')
        backup = os.environ.get('SOSO_ASSET_BACKUP')
        if not backup or asset_storage.parse(backup).provider != 's3':
            raise ValueError('CI backup verification requires a configured S3 destination.')
        print(f'Storage destination: {backup}')
        assets = asset_sync.records(asset_sync.DEFAULT_MANIFEST)
        return 0 if asset_sync.verify_assets(assets, asset_sync.DEFAULT_CACHE, backup) else 1
    except (ValueError, RuntimeError, OSError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
