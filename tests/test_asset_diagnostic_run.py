import base64
import contextlib
import io
import json
import unittest
from unittest.mock import patch

from soso.assets import asset_diagnostic_run as diagnostic


class DiagnosticRunTests(unittest.TestCase):
    def test_uses_only_exact_dispatched_run_and_its_verified_job(self):
        repo, commit = 'owner/repo', 'a' * 40
        account = {'full_name': repo}
        responses = {
            'workflows/inspect-asset-identity.yml': {'id': 42, 'path': '.github/workflows/inspect-asset-identity.yml'},
            'workflows/inspect-asset-identity.yml/dispatches': {'workflow_run_id': 8},
            'runs/8': dict(id=8, workflow_id=42, head_sha=commit, head_branch='main',
                           event='workflow_dispatch', run_attempt=1, repository=account, head_repository=account,
                           status='completed', conclusion='success'),
            'runs/8/attempts/1/jobs': dict(total_count=1, jobs=[
                dict(id=7, name='inspect', conclusion='success', run_id=8, head_sha=commit,
                     steps=[dict(name='Show identity only (no cloud access)', conclusion='success')])]),
        }
        subject = 'repo:owner@123/repo@456:ref:refs/heads/main'
        logs = f'2026-11-19T01:00:00.000Z {json.dumps(dict(sub=subject, aud="sts.amazonaws.com"), separators=(",", ":"))}\n'.encode()
        calls = []
        def api(path, *args, data=None):
            if path == f'repos/{repo}/git/ref/heads/main':
                return json.dumps({'object': {'sha': commit}}).encode()
            endpoint = path.split('/actions/', 1)[1]
            calls.append(endpoint)
            if endpoint.endswith('/dispatches'):
                self.assertEqual(json.loads(data), {'ref': 'main', 'return_run_details': True})
            if endpoint == 'jobs/7/logs':
                self.assertEqual(args, ('--allow-escape-sequences',))
                return b'\x1b[32mNever print the raw log\x1b[0m\n' + logs
            self.assertNotIn('--allow-escape-sequences', args)
            return json.dumps(responses[endpoint]).encode()
        with patch.object(diagnostic, 'api', side_effect=api), contextlib.redirect_stdout(io.StringIO()) as printed:
            self.assertEqual(diagnostic.run(repo, commit), subject)
            self.assertEqual(calls.count('workflows/inspect-asset-identity.yml/dispatches'), 1)
            self.assertEqual(calls[-1], 'jobs/7/logs')
            calls.clear()
            self.assertEqual(diagnostic.verify_run(repo, commit, 42, 8), subject)
            self.assertEqual(calls, ['runs/8', 'runs/8/attempts/1/jobs', 'jobs/7/logs'])
            responses['runs/8']['head_sha'] = 'b' * 40
            with self.assertRaisesRegex(ValueError, 'outside the approved'):
                diagnostic.run(repo, commit)
            self.assertEqual(calls[-1], 'runs/8')
            self.assertNotIn('Never print the raw log', printed.getvalue())
            self.assertNotIn(subject, printed.getvalue())

    def test_missing_dispatch_id_does_not_guess_or_retry(self):
        with patch.object(diagnostic, 'document', side_effect=[
            {'id': 42, 'path': '.github/workflows/inspect-asset-identity.yml'}, {'object': {'sha': 'a' * 40}}, {}
        ]) as api:
            with self.assertRaisesRegex(ValueError, 'exact run ID'):
                diagnostic.run('owner/repo', 'a' * 40)
            self.assertEqual(api.call_count, 3)

    def test_recovers_only_with_exact_historical_template(self):
        repo, commit, run_id = 'owner/repo', 'a' * 40, 8
        path = '.github/workflows/inspect-asset-identity.yml'
        details = dict(id=run_id, workflow_id=42, head_sha=commit, head_branch='main',
                       path=path + '@main', event='workflow_dispatch', run_attempt=1,
                       repository={'full_name': repo}, head_repository={'full_name': repo})
        template = b'trusted workflow\n'
        content = dict(type='file', encoding='base64', content=base64.b64encode(template).decode())
        with patch.object(diagnostic, 'document', side_effect=[details, content]) as api, \
                patch.object(diagnostic, 'verify_run', return_value='subject') as verify:
            self.assertEqual(diagnostic.recover(repo, run_id, template), 'subject')
            self.assertEqual([call.args for call in api.call_args_list], [
                (f'repos/{repo}/actions/runs/{run_id}',),
                (f'repos/{repo}/contents/{path}?ref={commit}',),
            ])
            verify.assert_called_once_with(repo, commit, 42, run_id)
        with patch.object(diagnostic, 'document', side_effect=[details, content]), \
                patch.object(diagnostic, 'verify_run') as verify:
            with self.assertRaisesRegex(ValueError, 'differs'):
                diagnostic.recover(repo, run_id, b'other file')
            verify.assert_not_called()

    def test_gone_is_distinct_from_ambiguous_errors(self):
        from subprocess import CompletedProcess
        for code in (404, 410, 503):
            with self.subTest(code=code), patch.object(diagnostic.subprocess, 'run',
                    return_value=CompletedProcess([], 1, b'', f'gh: unavailable (HTTP {code})\n'.encode())):
                with self.assertRaises(ValueError) as result:
                    diagnostic.recover('owner/repo', 8, b'workflow')
                self.assertEqual(isinstance(result.exception, diagnostic.DiagnosticUnavailable), code == 410)
