"""Azure setup contract tests; no live cloud calls or credentials."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from soso.assets import asset_setup_azure as setup


class AzureSetupTests(unittest.TestCase):
    def config(self):
        return setup.configuration('az://sosobackup/originals/2027',
            '11111111-1111-1111-1111-111111111111', '22222222-2222-2222-2222-222222222222', 'soso', 'eastus')

    def test_preview_and_verify_never_write(self):
        c = self.config()
        with tempfile.TemporaryDirectory() as temporary, patch.object(setup, 'verify') as check:
            out = Path(temporary) / 'not-created'
            answers = iter(['', '', '', '', 'existing'])
            self.assertEqual(setup.guided_setup(c['backup'], out, lambda _: next(answers),
                                               saved=c, dry_run=True), 0)
            self.assertEqual(check.call_args.kwargs, {'require_empty': True})
            self.assertFalse(out.exists())
            self.assertEqual(setup.verify_saved(c), 0)
            self.assertEqual(check.call_args.kwargs, {'require_empty': False})

    def responses(self):
        c = self.config()
        return [dict(id=c['subscription'], tenantId=c['tenant'], environmentName='AzureCloud'),
                dict(id=c['scope'], location='eastus', allowBlobPublicAccess=False,
                     allowSharedKeyAccess=False, enableHttpsTrafficOnly=True, minimumTlsVersion='TLS1_2',
                     encryption={'services': {'blob': {'enabled': True}}}),
                dict(name='originals', properties={'publicAccess': None}),
                {'policy': {'rules': []}},
                dict(isVersioningEnabled=False, deleteRetentionPolicy={'enabled': False}, containerDeleteRetentionPolicy={'enabled': False}), []]

    def test_validation(self):
        for destination in ('az://bad-/originals', 'az://sosobackup/originals/a/../b', 's3://wrong/path'):
            with self.assertRaises(ValueError):
                c = self.config()
                setup.configuration(destination, c['subscription'], c['tenant'], c['group'], c['location'])

    def test_read_only_verified_and_scoped(self):
        with patch.object(setup, 'read_state', return_value=self.responses()) as run, contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(setup.verify(self.config()))
        run.assert_called_once_with(self.config(), True)

    def test_failed_or_malformed_verification(self):
        changes = [(0, {}), (1, {}), (2, {}), (3, {}), (4, {}), (5, {}), (5, [{'name': 'old'}])]
        for index, value in changes:
            responses = self.responses()
            responses[index] = value
            with patch.object(setup, 'read_state', return_value=responses), contextlib.redirect_stdout(io.StringIO()), self.assertRaises(ValueError):
                setup.verify(self.config())
        responses = self.responses()
        responses[3]['policy']['rules'] = [{'enabled': True}]
        with patch.object(setup, 'read_state', return_value=responses), self.assertRaises(ValueError):
            setup.verify(self.config())

    def test_public_shared_key_and_identity_fail(self):
        for field, value in [('allowBlobPublicAccess', True), ('allowSharedKeyAccess', True), ('minimumTlsVersion', None), ('id', 'wrong')]:
            responses = self.responses()
            responses[1][field] = value
            with patch.object(setup, 'read_state', return_value=responses), self.assertRaises(ValueError):
                setup.verify(self.config())

    def test_plan_does_not_run_cloud_commands(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(setup, 'read_state') as run, contextlib.redirect_stdout(io.StringIO()) as out:
            setup.plan(self.config(), Path(folder))
            run.assert_not_called()
            self.assertFalse((Path(folder) / 'azure-config.json').exists())
            for text in ('PLAN ONLY', 'NOT just the prefix', 'NO password', '--auth-mode login', 'downloads no objects'):
                self.assertIn(text, out.getvalue())

    def test_create_only_plans_and_returns_incomplete(self):
        c = self.config()
        answers = iter([c['subscription'], c['tenant'], c['group'], c['location'], 'create'])
        with tempfile.TemporaryDirectory() as folder, patch.object(setup, 'read_state') as run, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(setup.guided_setup(c['backup'], Path(folder), lambda _: next(answers)), 1)
            run.assert_not_called()

    def test_initialized_rerun_rechecks_without_requiring_empty(self):
        saved = {**self.config(), 'provider': 'azure', 'initialized': True}
        answers = iter(['', '', '', '', '', '', '', '', 'y'])
        with tempfile.TemporaryDirectory() as folder, patch.object(setup, 'plan'), patch.object(setup, 'verify', return_value=True) as verify, patch('soso.assets.asset_setup.save_storage_config', create=True) as save, contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(setup.guided_setup(output=Path(folder), ask=lambda _: next(answers), saved=saved), 0)
            verify.assert_called_once_with(self.config(), require_empty=False)
            save.assert_called_once_with(saved, Path(folder))
            self.assertIn('existing objects are retained', out.getvalue())

    def test_changed_or_uninitialized_destination_requires_empty(self):
        for initialized, backup in [(False, self.config()['backup']), (True, 'az://sosobackup/originals/different')]:
            saved = {**self.config(), 'provider': 'azure', 'initialized': initialized}
            answers = iter(['', '', '', '', 'existing', 'y'])
            with tempfile.TemporaryDirectory() as folder, patch.object(setup, 'plan'), patch.object(setup, 'verify', return_value=True) as verify, patch('soso.assets.asset_setup.save_storage_config', create=True), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(setup.guided_setup(backup, Path(folder), lambda _: next(answers), saved=saved), 0)
                self.assertTrue(verify.call_args.kwargs['require_empty'])

    def test_failed_verification_does_not_save(self):
        c = self.config()
        answers = iter([c['subscription'], c['tenant'], c['group'], c['location'], 'existing', 'y'])
        with tempfile.TemporaryDirectory() as folder, patch.object(setup, 'plan'), patch.object(setup, 'verify', side_effect=ValueError('denied')), patch('soso.assets.asset_setup.save_storage_config', create=True) as save, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(setup.guided_setup(c['backup'], Path(folder), lambda _: next(answers)), 1)
            save.assert_not_called()

    def test_declined_and_create_plans_save_only_unverified_defaults(self):
        c = self.config()
        for mode in ('existing', 'create'):
            answers = [c['subscription'], c['tenant'], c['group'], c['location'], mode]
            if mode == 'existing':
                answers.append('n')
            answers = iter(answers)
            with tempfile.TemporaryDirectory() as folder, patch.object(setup, 'plan'), patch.object(setup, 'verify') as verify, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(setup.guided_setup(c['backup'], Path(folder), lambda _: next(answers)), 1)
                saved = json.loads((Path(folder) / 'storage-config.json').read_text())
                self.assertFalse(saved['initialized'])
                self.assertEqual(saved['provider'], 'azure')
                self.assertEqual(saved['backup'], c['backup'])
                verify.assert_not_called()

    def test_decline_preserves_only_exact_scope_initialized_marker(self):
        for backup, expected in [(self.config()['backup'], True), ('az://sosobackup/originals/other', False)]:
            saved = {**self.config(), 'provider': 'azure', 'initialized': True}
            answers = iter(['', '', '', '', 'existing', 'n'])
            with tempfile.TemporaryDirectory() as folder, patch.object(setup, 'plan'), patch.object(setup, 'verify') as verify, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(setup.guided_setup(backup, Path(folder), lambda _: next(answers), saved=saved), 1)
                updated = json.loads((Path(folder) / 'storage-config.json').read_text())
                self.assertEqual(updated['initialized'], expected)
                verify.assert_not_called()

    def test_saved_prefix_can_be_explicitly_cleared(self):
        saved = {**self.config(), 'provider': 'azure', 'initialized': True}
        answers = iter(['', '', '-', '', '', '', '', 'existing', 'y'])
        with tempfile.TemporaryDirectory() as folder, patch.object(setup, 'plan'), patch.object(setup, 'verify', return_value=True) as verify, patch('soso.assets.asset_setup.save_storage_config', create=True), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(setup.guided_setup(output=Path(folder), ask=lambda _: next(answers), saved=saved), 0)
            self.assertEqual(verify.call_args.args[0]['prefix'], '')
            self.assertTrue(verify.call_args.kwargs['require_empty'])



if __name__ == '__main__':
    unittest.main()
