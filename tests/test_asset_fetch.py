import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from soso.assets import asset_fetch as f, asset_sync


class FetchTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.cache = Path(scratch.name)
        self.original = b'exact original'
        self.sha = hashlib.sha256(self.original).hexdigest()
        self.row = {'id': 'photo', 'url': 'https://example.org/photo.jpg', 'sha256': self.sha}
        self.target = self.cache / asset_sync.key(self.sha)

    def test_cache_hit_ignores_public_and_private(self):
        self.target.parent.mkdir(parents=True)
        self.target.write_bytes(self.original)
        sources, backup = Mock(), Mock()
        self.assertEqual(f.fetch(self.row, self.cache, sources, backup), self.target)
        sources.download.assert_not_called()
        backup.assert_not_called()

    def test_mismatch_falls_back_to_verified_private_original(self):
        sources = Mock()
        sources.download.side_effect = lambda url, file: file.write_bytes(b'changed')
        with patch.object(f.asset_storage, 'transfer') as transfer:
            def retrieve(storage, operation, sha, file, **kwargs):
                self.assertFalse(file.exists())
                self.assertEqual((operation, sha), ('get', self.sha))
                file.write_bytes(self.original)
            transfer.side_effect = retrieve
            self.assertEqual(f.fetch(self.row, self.cache, sources, lambda: 's3://bucket'), self.target)
            self.assertEqual(self.target.read_bytes(), self.original)

    def test_bad_backup_never_promoted(self):
        sources = Mock()
        sources.download.side_effect = OSError('unavailable')
        with patch.object(f.asset_storage, 'transfer', side_effect=lambda *args, **kw: args[3].write_bytes(b'wrong')):
            with self.assertRaisesRegex(RuntimeError, 'Backup SHA-256 mismatch'):
                f.fetch(self.row, self.cache, sources, lambda: 's3://bucket')
        self.assertFalse(self.target.exists())

    def test_public_only_never_resolves_or_uses_private_storage(self):
        with patch('sys.argv', ['asset_fetch', '--public-only']), \
             patch.object(asset_sync, 'records', return_value=[self.row]), \
             patch.object(asset_sync, 'DEFAULT_CACHE', self.cache), \
             patch.object(asset_sync, 'configured_destination') as backup, \
             patch.object(f.asset_storage, 'transfer') as transfer, \
             patch.object(f.PublicSources, 'download', side_effect=OSError('unavailable')), \
             patch('sys.stderr', new_callable=io.StringIO) as err:
            with self.assertRaises(SystemExit):
                f.main()
            self.assertIn('photo', err.getvalue())
            backup.assert_not_called()
            transfer.assert_not_called()

    def test_ci_backup_fills_only_missing_hashes_without_public_fetch(self):
        cached = self.original + b' cached'
        cached_sha = hashlib.sha256(cached).hexdigest()
        cached_path = self.cache / asset_sync.key(cached_sha)
        cached_path.parent.mkdir(parents=True)
        cached_path.write_bytes(cached)
        rows = [self.row, {**self.row, 'sha256': cached_sha}]
        env = dict(GITHUB_ACTIONS='true', GITHUB_REF='refs/heads/main',
                   GITHUB_EVENT_NAME='push', SOSO_ASSET_BACKUP='s3://bucket')
        with patch('sys.argv', ['asset_fetch', '--ci-backup']), \
             patch.dict(f.os.environ, env, clear=True), \
             patch.object(asset_sync, 'records', return_value=rows), \
             patch.object(asset_sync, 'DEFAULT_CACHE', self.cache), \
             patch.object(f.PublicSources, 'download') as public, \
             patch.object(f.asset_storage, 'transfer', side_effect=lambda *a, **k: a[3].write_bytes(self.original)) as get:
            f.main()
        public.assert_not_called()
        self.assertEqual(get.call_count, 1)
        self.assertEqual(get.call_args.args[2], self.sha)
        self.assertEqual(self.target.read_bytes(), self.original)
        self.assertEqual(cached_path.read_bytes(), cached)

    def test_ci_backup_names_missing_original_without_trying_public_sources(self):
        env = dict(GITHUB_ACTIONS='true', GITHUB_REF='refs/heads/main',
                   GITHUB_EVENT_NAME='workflow_dispatch', SOSO_ASSET_BACKUP='s3://bucket')
        with patch('sys.argv', ['asset_fetch', '--ci-backup']), \
             patch.dict(f.os.environ, env, clear=True), \
             patch.object(asset_sync, 'records', return_value=[self.row]), \
             patch.object(asset_sync, 'DEFAULT_CACHE', self.cache), \
             patch.object(f, 'PublicSources') as public, \
             patch.object(f.asset_storage, 'transfer', side_effect=OSError('NoSuchKey')) as get, \
             patch('sys.stderr', new_callable=io.StringIO) as err:
            with self.assertRaises(SystemExit) as status:
                f.main()
            self.assertEqual(status.exception.code, 1)
        public.assert_not_called()
        get.assert_called_once()
        self.assertFalse(self.target.exists())
        self.assertIn('photo', err.getvalue())
        self.assertIn('NoSuchKey', err.getvalue())

    def test_ci_backup_refuses_pr_branch_and_non_actions(self):
        env = dict(GITHUB_ACTIONS='true', GITHUB_REF='refs/heads/main',
                   GITHUB_EVENT_NAME='push', SOSO_ASSET_BACKUP='s3://bucket')
        for expected in ({'GITHUB_ACTIONS': 'false'}, {'GITHUB_EVENT_NAME': 'pull_request'},
                         {'GITHUB_REF': 'refs/heads/work'}, {'SOSO_ASSET_BACKUP': 'gs://bucket'}):
            with self.subTest(expected=expected), patch.dict(f.os.environ, {**env, **expected}, clear=True):
                with self.assertRaises(ValueError):
                    f.ci_backup_destination()

    def test_symlink_escape_rejected(self):
        cache = self.cache / 'cache'
        cache.mkdir()
        (cache / 'sha256').symlink_to(self.cache, target_is_directory=True)
        sources = Mock()
        with self.assertRaisesRegex(ValueError, 'symlink'):
            f.fetch(self.row, cache, sources)
        sources.download.assert_not_called()

    def test_two_jittered_retries(self):
        clock = [0]
        waits = []
        def sleep(seconds):
            waits.append(seconds)
            clock[0] += seconds
        with patch.object(f.urllib.request, 'urlopen', side_effect=URLError('offline')) as get, \
             patch.object(f.time, 'monotonic', side_effect=lambda: clock[0]), \
             patch.object(f.time, 'sleep', side_effect=sleep), \
             patch.object(f.random, 'uniform', side_effect=[0.8, 1.2]):
            with self.assertRaises(URLError):
                f.PublicSources().download(self.row['url'], self.target)
        self.assertEqual(get.call_count, 3)
        self.assertEqual(waits, [8, 72])

    def test_retry_after_boundary_and_permanent_failure(self):
        for status, headers, retry in [
            (429, {'Retry-After': '300'}, True),
            (503, {'Retry-After': '301'}, False),
            (404, {}, False),
        ]:
            with self.subTest(status=status):
                url = self.row['url']
                error = HTTPError(url, status, 'busy', headers, None)
                response = io.BytesIO(self.original)
                response.url = url
                with patch.object(f.urllib.request, 'urlopen', side_effect=[error, response]) as get, \
                     patch.object(f.time, 'monotonic', side_effect=[0, 0, 300, 300]), \
                     patch.object(f.time, 'sleep') as sleep:
                    if retry:
                        f.PublicSources().download(url, self.cache / 'original')
                        self.assertEqual(get.call_count, 2)
                        sleep.assert_called_once_with(300)
                    else:
                        with self.assertRaises(HTTPError):
                            f.PublicSources().download(url, self.cache / 'original')
                        get.assert_called_once()
                        sleep.assert_not_called()

    def test_long_wait_pauses_both_wikimedia_hosts(self):
        url = 'https://upload.wikimedia.org/x'
        err = HTTPError(url, 429, 'busy', {'Retry-After': '301'}, None)
        sources = f.PublicSources()
        with patch.object(f.urllib.request, 'urlopen', side_effect=err) as get:
            with self.assertRaises(HTTPError):
                sources.download(url, self.target)
            with self.assertRaisesRegex(ValueError, 'paused'):
                sources.download('https://thumb.wikimedia.org/y', self.target)
            get.assert_called_once()
