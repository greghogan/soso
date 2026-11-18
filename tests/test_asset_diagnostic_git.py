import contextlib
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from soso.assets import asset_diagnostic_git as diagnostic


class DiagnosticGitTests(unittest.TestCase):
    def test_publish_leaves_diverged_local_branch_and_index_untouched(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()) as output:
            root = Path(folder)
            remote, local = root / 'remote', root / 'local'
            env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1',
                       GIT_AUTHOR_NAME='Tester', GIT_AUTHOR_EMAIL='test@example.com',
                       GIT_COMMITTER_NAME='Tester', GIT_COMMITTER_EMAIL='test@example.com')
            def git(path, *args):
                return subprocess.check_output(['git', '-C', str(path), *args], env=env,
                                               stderr=subprocess.PIPE).strip()
            git(root, 'init', '--bare', '--initial-branch=main', str(remote))
            git(root, 'init', '--initial-branch=main', str(local))
            git(local, 'commit', '--allow-empty', '-m', 'base')
            git(local, 'remote', 'add', 'origin', str(remote))
            git(local, 'push', 'origin', 'main')
            base = git(remote, 'rev-parse', 'main')
            git(local, 'commit', '--allow-empty', '-m', 'local-only')
            local_head = git(local, 'rev-parse', 'HEAD')
            (local / 'other').write_text('user work')
            git(local, 'add', 'other')
            staged = git(local, 'write-tree')
            probe = root / 'probe.yml'
            probe.write_text('name: Diagnostic\n')
            with patch.dict(os.environ, env), patch.object(diagnostic, 'github_origin'):
                self.assertFalse(diagnostic.publish(local, 'example/test', probe, lambda _: ''))
                self.assertEqual(git(remote, 'rev-parse', 'main'), base)
                published = diagnostic.publish(local, 'example/test', probe, lambda _: 'y')
                self.assertEqual(git(remote, 'rev-parse', 'main'), published.encode())
                self.assertEqual(diagnostic.publish(local, 'example/test', probe, lambda _: 'y'), published)
            self.assertEqual(git(local, 'rev-parse', 'HEAD'), local_head)
            self.assertEqual(git(local, 'write-tree'), staged)
            self.assertEqual(git(remote, 'rev-parse', 'main^'), base)
            self.assertEqual(git(remote, 'diff-tree', '--no-commit-id', '--name-only', '-r', 'main'), diagnostic.WORKFLOW.encode())
            self.assertIn('publish only the diagnostic to example/test main and run it', output.getvalue())
            self.assertIn('may trigger Pages', output.getvalue())
            self.assertNotIn('name: Diagnostic', output.getvalue())
