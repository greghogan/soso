import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from soso.assets import asset_setup_s3compatible as setup, asset_storage as storage

class SetupTests(unittest.TestCase):
    def test_preview_is_read_only_and_verify_rejects_changed_account(self):
        saved = {'provider': 'r2', 'backup': 'r2://bucket', 'endpoint_identity': 'a' * 32}
        with tempfile.TemporaryDirectory() as temporary, patch.object(setup, 'check_endpoint') as check:
            out = Path(temporary) / 'not-created'
            self.assertEqual(setup.guided_setup('r2', saved['backup'], out, lambda _: 'existing',
                                               dry_run=True), 1)
            self.assertEqual(check.call_args.kwargs, {'require_empty': True})
            self.assertFalse(out.exists())
            check.reset_mock()
            with patch.dict(os.environ, {'SOSO_R2_ACCOUNT_ID': 'b' * 32}):
                with self.assertRaisesRegex(ValueError, 'does not match'):
                    setup.verify_saved(saved)
                check.assert_not_called()
            with patch.dict(os.environ, {'SOSO_R2_ACCOUNT_ID': 'a' * 32}):
                self.assertEqual(setup.verify_saved(saved), 1)
            self.assertEqual(check.call_args.kwargs, {'require_empty': False})

    def test_plan_never_claims_complete(self):
        for provider in ('r2','b2'):
            with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()) as out:
                answers=iter(['new','n'])
                self.assertEqual(setup.guided_setup(provider,f'{provider}://bucket',Path(tmp),lambda _:next(answers)),1)
                self.assertIn('UNVERIFIED',out.getvalue())
                self.assertFalse((Path(tmp)/f'{provider}-config.json').exists())
                config=json.loads((Path(tmp)/'storage-config.json').read_text())
                self.assertEqual(config['backup'],f'{provider}://bucket')
                self.assertFalse(config['initialized'])
                self.assertEqual(config['status'],'unverified-plan')

    def test_skipped_initial_check_does_not_waive_future_emptiness(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'SOSO_R2_ACCOUNT_ID':'a'*32}), contextlib.redirect_stdout(io.StringIO()):
            answers=iter(['existing','n'])
            setup.guided_setup('r2','r2://bucket/path',Path(tmp),lambda _:next(answers))
            config_path=Path(tmp)/'storage-config.json'
            saved=json.loads(config_path.read_text())
            self.assertFalse(saved['initialized'])
            answers=iter(['','y'])
            with patch.object(storage,'compatible_run',return_value='{"KeyCount":1,"Contents":[{"Key":"path/object"}],"IsTruncated":false}'):
                setup.guided_setup('r2',saved['backup'],Path(tmp),lambda _:next(answers),saved=saved)
            self.assertFalse(json.loads(config_path.read_text())['initialized'])

    def test_skipped_rerun_preserves_only_exact_adoption_marker(self):
        saved={'provider':'r2','backup':'r2://bucket/path','mode':'existing','initialized':True,
               'endpoint_identity':'a'*32}
        for destination, expected in [('r2://bucket/path',True),('r2://bucket/other',False)]:
            with self.subTest(destination=destination), tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'SOSO_R2_ACCOUNT_ID':'a'*32}), contextlib.redirect_stdout(io.StringIO()):
                answers=iter(['existing','n'])
                setup.guided_setup('r2',destination,Path(tmp),lambda _:next(answers),saved=saved)
                c=json.loads((Path(tmp)/'storage-config.json').read_text())
                self.assertEqual(c['initialized'],expected)
                self.assertEqual(c['status'],'unverified-plan')

    def test_live_check_not_full_verification(self):
        with patch.dict(os.environ, {'SOSO_R2_ACCOUNT_ID':'a'*32}), tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()) as out, patch.object(storage,'compatible_run',return_value='{"KeyCount":0,"IsTruncated":false}') as run:
            answers=iter(['existing','y'])
            self.assertEqual(setup.guided_setup('r2','r2://bucket/path',Path(tmp),lambda _:next(answers)),1)
            self.assertIn('path/',run.call_args.args)
            self.assertIn('empty live prefix only',out.getvalue())

    def test_saved_rerun_accepts_existing_objects_without_claiming_empty(self):
        saved={'provider':'r2','backup':'r2://bucket/path','mode':'existing','initialized':True,
               'status':'endpoint-verified-security-unverified','endpoint_identity':'a'*32}
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'SOSO_R2_ACCOUNT_ID':'a'*32}), contextlib.redirect_stdout(io.StringIO()) as out:
            answers=iter(['','','','y'])
            listing='{"KeyCount":1,"Contents":[{"Key":"path/sha256/aa/key"}],"IsTruncated":true,"NextContinuationToken":"next"}'
            with patch.object(storage,'compatible_run',return_value=listing) as read:
                self.assertEqual(setup.guided_setup('r2',output=Path(tmp),ask=lambda _:next(answers),saved=saved),1)
            self.assertIn('existing prefix contents preserved',out.getvalue())
            self.assertNotIn('VERIFIED: endpoint access and empty',out.getvalue())
            self.assertIn('bucket privacy',out.getvalue())
            import json
            config=json.loads((Path(tmp)/'storage-config.json').read_text())
            self.assertEqual(config['backup'],'r2://bucket/path')
            self.assertTrue(config['initialized'])
            self.assertIn('path/',read.call_args.args)

    def test_changed_destination_or_endpoint_requires_empty_again(self):
        saved={'provider':'r2','backup':'r2://bucket/path','mode':'existing','initialized':True,
               'endpoint_identity':'a'*32}
        for backup, endpoint in [('r2://other/path','a'*32),('r2://bucket/path','b'*32)]:
            with self.subTest(backup=backup,endpoint=endpoint), tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'SOSO_R2_ACCOUNT_ID':endpoint}), contextlib.redirect_stdout(io.StringIO()):
                answers=iter(['existing','y'])
                with patch.object(storage,'compatible_run',return_value='{"KeyCount":1,"Contents":[{"Key":"path/object"}],"IsTruncated":false}'):
                    self.assertEqual(setup.guided_setup('r2',backup,Path(tmp),lambda _:next(answers),saved=saved),1)
                self.assertFalse((Path(tmp)/'storage-config.json').exists())

    def test_saved_b2_rechecks_lifecycle_before_save(self):
        saved={'provider':'b2','backup':'b2://bucket/path','mode':'existing','initialized':True,
               'endpoint_identity':'us-west-004'}
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'SOSO_B2_REGION':'us-west-004'}), contextlib.redirect_stdout(io.StringIO()):
            answers=iter(['','y'])
            with patch.object(storage,'compatible_run',return_value='{"KeyCount":0,"IsTruncated":false}'), patch.object(storage,'verify_b2_retention',side_effect=ValueError('expiration')) as lifecycle:
                self.assertEqual(setup.guided_setup('b2',saved['backup'],Path(tmp),lambda _:next(answers),saved=saved),1)
                lifecycle.assert_called_once()
            self.assertFalse((Path(tmp)/'storage-config.json').exists())

    def test_untrusted_endpoint_inputs_fail_before_sdk_request(self):
        for provider, variable, value in [('r2','ACCOUNT_ID','a'*32+'.evil'),('b2','REGION','us-west-004.evil')]:
            stem='SOSO_'+provider.upper()+'_'
            env={stem+'ACCESS_KEY_ID':'key',stem+'SECRET_ACCESS_KEY':'secret',stem+variable:value}
            with patch.dict(os.environ,env,clear=True), patch('boto3.Session') as session:
                with self.assertRaises(ValueError): storage.compatible_run(provider,'s3api','get-object')
                session.assert_not_called()
