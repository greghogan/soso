"""Fetch exact manifest originals into the local cache, with private storage as fallback."""
import argparse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import math
import os
from pathlib import Path
import random
import sys
import tempfile
import time
import urllib.error
from urllib.parse import urlsplit
import urllib.request

from . import asset_storage, asset_sync

USER_AGENT = 'SOSO-asset-fetch/1.0'
BACKOFF = (10, 60)
MAX_RETRY_AFTER = 300
RETRYABLE = {408, 429, 500, 502, 503, 504}


def retry_delay(error, attempt):
    value = error.headers.get('Retry-After') if isinstance(error, urllib.error.HTTPError) and error.headers else None
    if value:
        try:
            delay = float(value)
        except ValueError:
            try:
                date = parsedate_to_datetime(value)
                delay = max(0, (date - datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError, OverflowError):
                delay = math.nan
        if delay > MAX_RETRY_AFTER:
            return None  # Don't retry before the source allows it.
        if math.isfinite(delay) and delay >= 0:
            return delay
    return BACKOFF[attempt] * random.uniform(0.8, 1.2)


class PublicSources:
    """Pace requests by service and stop hitting a provider that is still throttling."""
    def __init__(self):
        self.last_request = {}
        self.paused = set()

    def download(self, url, candidate):
        host = urlsplit(url).hostname or ''
        service = 'wikimedia.org' if host.endswith('.wikimedia.org') else host
        if service in self.paused:
            raise ValueError(f'{service} paused after rate limiting earlier in this run')
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        for attempt in range(len(BACKOFF) + 1):
            remaining = self.last_request.get(service, -math.inf) + 1 - time.monotonic()
            if remaining > 0:
                time.sleep(remaining)
            self.last_request[service] = time.monotonic()
            try:
                with urllib.request.urlopen(req, timeout=60) as response, candidate.open('wb') as output:
                    if not response.url.startswith('https://'):
                        raise ValueError('Non-HTTPS redirect rejected')
                    size = 0
                    for block in iter(lambda: response.read(1024 * 1024), b''):
                        size += len(block)
                        if size > 256 * 1024 * 1024:
                            raise ValueError('Source exceeds 256 MiB limit')
                        output.write(block)
                return
            except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
                status = error.code if isinstance(error, urllib.error.HTTPError) else None
                if status is not None and status not in RETRYABLE:
                    raise
                if attempt == len(BACKOFF):
                    if status == 429 or (status is not None and error.headers and error.headers.get('Retry-After')):
                        self.paused.add(service)
                    raise
                delay = retry_delay(error, attempt)
                if delay is None:
                    self.paused.add(service)
                    raise
                print(f'{service}: retrying in {delay:.1f}s ({error})', file=sys.stderr)
                time.sleep(delay)


def fetch(record, cache, sources, resolve_backup=None):
    sha = record['sha256']
    target = cache / asset_sync.key(sha)
    if not target.parent.resolve().is_relative_to(cache.resolve()):
        raise ValueError('Refusing cache path that escapes through a symlink')
    if asset_sync.verified(target, sha):
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    errors = []
    with tempfile.TemporaryDirectory(prefix='.fetch-', dir=target.parent) as tmp:
        candidate = Path(tmp) / 'original'
        if sources is not None:
            try:
                sources.download(record['url'], candidate)
                if not asset_sync.verified(candidate, sha):
                    raise ValueError('Public source changed: SHA-256 mismatch')
                candidate.replace(target)
                return target
            except (OSError, ValueError) as exc:
                errors.append(f'public source: {exc}')
        if resolve_backup:
            try:
                backup = resolve_backup()
            except (ValueError, OSError) as exc:
                errors.append(f'backup configuration: {exc}')
                backup = None
        else:
            backup = None
        if backup:
            # Avoid ever accepting bytes left by the preceding public attempt.
            candidate.unlink(missing_ok=True)
            if sources is not None:
                print(f"{record['id']}: trying private backup; request and egress charges may apply.", file=sys.stderr)
            try:
                asset_storage.transfer(asset_storage.parse(backup), 'get', sha, candidate, aws=asset_sync.aws)
                if not asset_sync.verified(candidate, sha):
                    raise ValueError('Backup SHA-256 mismatch')
                candidate.replace(target)
                return target
            except Exception as exc:
                errors.append(f'backup: {exc}')
    raise RuntimeError(f"{record['id']} ({sha}): " + '; '.join(errors))


def ci_backup_destination():
    if (os.environ.get('GITHUB_ACTIONS') != 'true'
            or os.environ.get('GITHUB_REF') != 'refs/heads/main'
            or os.environ.get('GITHUB_EVENT_NAME') not in {'push', 'workflow_dispatch'}):
        raise ValueError('Private CI asset access is restricted to trusted main builds')
    value = os.environ.get('SOSO_ASSET_BACKUP')
    if not value or asset_storage.parse(value).provider != 's3':
        raise ValueError('Private CI asset access requires a configured S3 destination')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--public-only', action='store_true', help='Use the cache and pinned public sources; never read private storage')
    modes.add_argument('--ci-backup', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        rows = asset_sync.records(asset_sync.DEFAULT_MANIFEST)
        backup = ci_backup_destination() if args.ci_backup else None
    except (ValueError, OSError) as exc:
        parser.exit(1, f'ERROR: {exc}\n')
    sources = None if args.ci_backup else PublicSources()
    resolve_backup = (lambda: backup) if args.ci_backup else (None if args.public_only else asset_sync.configured_destination)
    missing = []
    for row in rows:
        try:
            # Resolve the saved endpoint only when an original actually needs private fallback.
            fetch(row, asset_sync.DEFAULT_CACHE, sources, resolve_backup)
        except (ValueError, RuntimeError, OSError) as exc:
            missing.append(str(exc))
    if missing:
        hint = 'Verify that ./scripts/asset_sync.py uploaded all originals and the CI role can read them.\n' if args.ci_backup else ''
        parser.exit(1, 'Missing verified originals (no placeholders used):\n' +
                    ''.join(f'  {item}\n' for item in missing) + hint)
    print(f'{len(rows)} originals verified.')


if __name__ == '__main__':
    main()
