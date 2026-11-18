"""Verified original-image cache and append-only cloud backup (native SDK credentials)."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import unquote, urlsplit

from . import asset_storage

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / 'manifests/external-assets.json'
DEFAULT_CACHE = ROOT / 'assets/cache'
DEFAULT_SETUP = ROOT / 'assets/setup'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def destination(value):
    value = value.removeprefix('s3://').rstrip('/')
    bucket, _, prefix = value.partition('/')
    if not re.fullmatch(r'[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]', bucket) or '..' in bucket or re.fullmatch(r'[0-9.]+', bucket):
        raise ValueError('Use a valid S3 bucket name, optionally followed by /prefix')
    if prefix and (not re.fullmatch(r'[A-Za-z0-9/_-]+', prefix) or any(x in ('', '.', '..') for x in prefix.split('/'))):
        raise ValueError('Prefix must contain simple nonempty slash-separated letters, numbers, underscores or hyphens')
    return bucket, prefix


def hash_value(value):
    if not re.fullmatch(r'[0-9a-f]{64}', value):
        raise ValueError('Expected a lowercase SHA-256 digest')
    return value


def key(sha):
    hash_value(sha)
    return f'sha256/{sha[:2]}/{sha}'


def s3_key(prefix, sha):
    return '/'.join(x for x in (prefix, key(sha)) if x)


def aws(*args):
    from .asset_aws import request
    return json.dumps(request(*args), default=str)


def records(path):
    return parse_records(path.read_text())


def parse_records(source):
    data = json.loads(source)['assets']
    if not isinstance(data, list):
        raise ValueError('Expected an asset list in the manifest')
    seen = set()
    for record in data:
        sha = hash_value(record['sha256'])
        if sha in seen:
            raise ValueError('Duplicate SHA-256 in asset manifest')
        seen.add(sha)
        url = record['url']
        if not url.startswith('https://'):
            raise ValueError('Asset source must be HTTPS')
    return data


def verified(path, sha):
    return path.is_file() and not path.is_symlink() and digest(path) == sha


def configured_destination(explicit=None):
    """Explicit destinations override saved defaults, not a saved endpoint binding."""
    target = asset_storage.parse(explicit) if explicit else None
    bindings = {'r2': 'SOSO_R2_ACCOUNT_ID', 'b2': 'SOSO_B2_REGION'}
    if target and target.provider not in bindings:
        return explicit
    from .asset_setup import load_storage_config
    saved = load_storage_config(DEFAULT_SETUP)
    if not saved:
        return explicit
    value = saved['backup']
    saved_target = asset_storage.parse(value)
    if target and target != saved_target:
        return explicit
    variable = bindings.get(saved_target.provider)
    if variable:
        endpoint = saved.get('endpoint_identity')
        if not endpoint or os.environ.get(variable) != endpoint:
            raise ValueError(f'Saved {saved_target.provider.upper()} destination {value} is not bound to the current '
                             f'{variable}. Restore the saved endpoint or verify setup before retrying.')
    return explicit or value


def upload(path, sha, backup):
    """Create-only upload followed by metadata checksum verification, never GET."""
    from . import asset_integrity
    if not verified(path, sha):
        raise ValueError('Refusing upload of unverified cache entry')
    return asset_integrity.upload(path, sha, asset_storage.parse(backup))


def verify_backup(record, cache, backup):
    """Compare service checksums without retrieving any object body."""
    from . import asset_integrity
    path = cache / key(record['sha256'])
    if path.exists():
        if not verified(path, record['sha256']):
            raise ValueError(f"Corrupt local cache entry: {record['id']}")
        expected = asset_integrity.record(path)
    else:
        if not isinstance(record.get('checksums'), dict):
            raise ValueError(f"Missing local checksums for {record['id']}; no backup download attempted")
        expected = {**record['checksums'], 'sha256': record['sha256']}
    storage = asset_storage.parse(backup)
    return asset_integrity.verify_record(expected, record['sha256'], storage)


def save_verification(cache, report):
    """Keep nonsecret service checksum evidence in the ignored local cache."""
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / 'verification.json'
    if target.is_symlink():
        raise ValueError('Refusing symlinked verification report')
    records = json.loads(target.read_text()) if target.exists() else {}
    if not isinstance(records, dict):
        raise ValueError('Invalid local verification report')
    records[report['uri']] = report
    with tempfile.NamedTemporaryFile(mode='w', dir=cache, prefix='.verification-', delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(records, stream, indent=2)
        stream.write('\n')
    try:
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def prune(hashes, active, backup):
    """Explicit known-key deletion only, never list or infer old objects are disposable."""
    storage = asset_storage.parse(backup)
    bucket = storage.bucket
    hashes = sorted(set(hash_value(x) for x in hashes))
    if set(hashes) & active:
        raise ValueError('Refusing deletion of currently referenced originals')
    if not hashes:
        raise ValueError('Specify at least one SHA-256')
    print('WARNING: These objects may be required by historical commits. This can break historical rebuilds.')
    print('No local files are deleted. Cloud versioning/soft deletion may retain older versions; this is not a storage purge.')
    for sha in hashes:
        print(storage.uri(sha))
    phrase = f'DELETE {len(hashes)} HISTORICAL OBJECTS FROM {bucket}'
    if not os.isatty(0) or input(f'Type exactly "{phrase}" to proceed: ') != phrase:
        raise ValueError('Deletion cancelled; interactive confirmation required')
    for sha in hashes:
        asset_storage.transfer(storage, 'delete', sha, aws=aws)
        print(f'Deletion requested: {sha} (historical versions not purged)')


def list_manifest_objects(storage, assets, *, verbose=False):
    """Return matching S3 object keys, or None when listing is unavailable."""
    if storage.provider != 's3':
        return None
    from botocore.exceptions import BotoCoreError, ClientError
    from . import asset_aws, asset_integrity
    wanted = {storage.object_key(row['sha256']) for row in assets}
    if not wanted:
        return set()
    prefix = '/'.join(part for part in (storage.prefix, 'sha256/') if part)
    found = set()
    try:
        sdk = asset_aws.client()
        for page in sdk.get_paginator('list_objects_v2').paginate(Bucket=storage.bucket, Prefix=prefix):
            found.update(obj['Key'] for obj in page.get('Contents', []) if obj['Key'] in wanted)
            if found == wanted:
                break
    except ClientError as exc:
        error = exc.response
        if error.get('Error', {}).get('Code') in {'AccessDenied', 'Forbidden', '403'} or error.get('ResponseMetadata', {}).get('HTTPStatusCode') == 403:
            if verbose:
                print('S3 listing unavailable; checking exact manifest keys.')
            return None
        raise RuntimeError(asset_integrity.s3_service_error(exc, 's3')) from None
    except BotoCoreError as exc:
        raise RuntimeError(asset_integrity.s3_service_error(exc, 's3')) from None
    return found


def verify_assets(assets, cache, backup, *, present=None, verbose=False):
    """Check metadata, report status, and return whether every object verified."""
    from .asset_integrity import BackupObjectMissing
    storage = asset_storage.parse(backup)
    print('Verifying stored originals...', flush=True)
    missing = 0
    for record in assets:
        try:
            if present is not None and storage.object_key(record['sha256']) not in present:
                raise BackupObjectMissing()
            report = verify_backup(record, cache, backup)
        except BackupObjectMissing:
            missing += 1
            if verbose:
                print(f"MISSING {record['id']} {record['sha256']}")
        except (ValueError, RuntimeError) as exc:
            raise RuntimeError(f'{record["id"]}: {exc}') from None
        else:
            save_verification(cache, report)
            if verbose:
                print(f"VERIFIED {record['id']} {record['sha256']}")
    print(f'Backup status: {len(assets) - missing}/{len(assets)} verified; {missing} not found.')
    return missing == 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--verify', action='store_true', help='Check backup checksum metadata without downloading')
    mode.add_argument('--delete', metavar='SHA256', action='append',
                      help='Preview and confirm deletion of an exact historical object (repeatable)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Show per-asset backup details')
    args = parser.parse_args()
    try:
        assets = records(DEFAULT_MANIFEST)
        backup = configured_destination()
        if not backup:
            raise ValueError('No backup configured. Run ./scripts/asset_setup.py first.')
        print(f'Storage destination: {backup}')
        if args.delete:
            prune(args.delete, {x['sha256'] for x in assets}, backup)
            return
        storage = asset_storage.parse(backup)
        if args.verify:
            present = list_manifest_objects(storage, assets, verbose=args.verbose)
            if not verify_assets(assets, DEFAULT_CACHE, backup, present=present, verbose=args.verbose):
                raise SystemExit(1)
            return
        missing = [record['id'] for record in assets
                   if not verified(DEFAULT_CACHE / key(record['sha256']), record['sha256'])]
        if missing:
            raise ValueError(f'{len(missing)} local originals are missing or corrupt. Run ./scripts/asset_fetch.py first.'
                             + (' Assets: ' + ', '.join(missing) if args.verbose else ''))
        present = list_manifest_objects(storage, assets, verbose=args.verbose)
        for record in assets:
            sha = record['sha256']
            if present is not None and storage.object_key(sha) in present:
                report = verify_backup(record, DEFAULT_CACHE, backup)
                if args.verbose:
                    print(f"ALREADY PRESENT {record['id']} {sha}")
            else:
                path = DEFAULT_CACHE / key(sha)
                filename = unquote(urlsplit(record.get('url', '')).path.rsplit('/', 1)[-1]) or record['id']
                filename = ''.join(c if c.isprintable() else '?' for c in filename)
                print(f'Uploading {filename} ({path.stat().st_size:,} bytes)', flush=True)
                report = upload(path, sha, backup)
                if args.verbose:
                    print(f"VERIFIED {record['id']} {sha}")
            save_verification(DEFAULT_CACHE, report)
        print(f'Backup status: {len(assets)}/{len(assets)} verified. No unreferenced files deleted.')
    except (ValueError, RuntimeError, OSError) as exc:
        parser.exit(1, f'ERROR: {exc}\n')


if __name__ == '__main__':
    main()
