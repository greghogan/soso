import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from soso.assets import pre_push

HOOK = Path(__file__).resolve().parents[1] / '.githooks/pre-push'
SHA = 'a' * 64
RECORD = {'id': 'pushed-original', 'sha256': SHA, 'url': 'https://example.org/photo.jpg'}


class AssetPrePushTests(unittest.TestCase):
    def test_shell_routes_only_non_deletion_pushes_to_origin_main(self):
        with tempfile.TemporaryDirectory() as folder:
            uv = Path(folder) / 'uv'
            uv.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\nexit 7\n')
            uv.chmod(0o755)
            branch = f'refs/heads/work {SHA} refs/heads/topic {SHA}\n'
            main = f'refs/heads/work {SHA} refs/heads/main {SHA}\n'
            delete = f'(delete) {"0" * 64} refs/heads/main {SHA}\n'
            for remote, refs, status in [
                ('fork', main, 0), ('origin', branch, 0),
                ('origin', delete, 0), ('origin', branch + main, 7),
            ]:
                with self.subTest(remote=remote, refs=refs):
                    result = subprocess.run(
                        [str(HOOK), remote, 'remote-url'], input=refs, text=True,
                        capture_output=True, env={**os.environ, 'PATH': folder},
                    )
                    self.assertEqual(result.returncode, status, result.stderr)
                    self.assertEqual(result.stdout.splitlines(), (
                        ['run', '--locked', 'python', '-m', 'soso.assets.pre_push', SHA] if status else []
                    ))

    def test_verifies_manifest_from_pushed_commit_and_blocks_missing_objects(self):
        for complete in (True, False):
            with self.subTest(complete=complete), \
                 patch.object(pre_push.subprocess, 'check_output', return_value=json.dumps({'assets': [RECORD]})) as git, \
                 patch.object(pre_push.asset_sync, 'configured_destination', return_value='s3://test-bucket'), \
                 patch.object(pre_push.asset_sync, 'list_manifest_objects', return_value=set()) as listing, \
                 patch.object(pre_push.asset_sync, 'verify_assets', return_value=complete) as verify, \
                 patch('builtins.print') as output:
                self.assertEqual(pre_push.main(SHA), 0 if complete else 1)
                git.assert_called_once_with(['git', 'show', f'{SHA}:manifests/external-assets.json'], text=True)
                self.assertEqual(listing.call_args.args[1], [RECORD])
                self.assertEqual(verify.call_args.args[0], [RECORD])
                self.assertEqual(verify.call_args.kwargs['present'], set())
                self.assertEqual(any('Run ./scripts/asset_sync.py' in str(call) for call in output.call_args_list),
                                 not complete)

    def test_unconfigured_storage_blocks_without_listing(self):
        with patch.object(pre_push.subprocess, 'check_output', return_value=json.dumps({'assets': [RECORD]})), \
             patch.object(pre_push.asset_sync, 'configured_destination', return_value=None), \
             patch.object(pre_push.asset_sync, 'list_manifest_objects') as listing, \
             patch('builtins.print'):
            self.assertEqual(pre_push.main(SHA), 1)
            listing.assert_not_called()
