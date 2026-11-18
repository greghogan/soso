"""No AWS calls: policy boundaries and fail-closed verification."""
import argparse
import contextlib
import io
import json
import re
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

import yaml

from soso.assets import asset_setup as setup


class AssetSetupTests(unittest.TestCase):
    def config(self, **overrides):
        args = dict(backup='s3://soso-private/backups', account='123456789012', repo='greghogan/soso',
                    region='us-east-1', role='soso-asset-read', subject='repo:greghogan/soso:ref:refs/heads/main')
        args.update(overrides)
        return setup.configuration(argparse.Namespace(**args))

    def test_verify_defaults_to_canonical_state(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            saved = self.config()
            setup.save_storage_config({**saved, 'provider': 's3'}, output)
            with patch.object(setup, 'DEFAULT_OUTPUT', output), patch.object(setup, 'verify', return_value=0) as verify, patch.object(setup, 'verify_github_variables', side_effect=(True, False)) as github:
                self.assertEqual(setup.main(['--verify']), 0)
                self.assertEqual(setup.main(['--verify']), 1)
                self.assertEqual(verify.call_count, 2)
                verify.assert_called_with(saved)
                github.assert_called_with(saved)

    def test_least_privilege(self):
        policies = setup.policies(self.config())
        read = policies['read.json']['Statement']
        self.assertEqual(read, [{'Effect': 'Allow', 'Action': ['s3:GetObject'], 'Resource': ['arn:aws:s3:::soso-private/backups/sha256/*']}])
        upload = policies['upload.json']['Statement'][1]
        self.assertEqual(upload['Action'], ['s3:PutObject'])
        self.assertEqual(upload['Condition'], {'StringEquals': {'s3:if-none-match': '*'}})
        condition = policies['trust.json']['Statement'][0]['Condition']
        self.assertEqual(condition['StringEquals'][setup.ISSUER + ':aud'], 'sts.amazonaws.com')
        self.assertNotIn('StringLike', condition)

    def test_subject_formats(self):
        for subject in ('repo:greghogan/soso:ref:refs/heads/main', 'repo:greghogan@123/soso@456:ref:refs/heads/main',
                        'repo:greghogan@123/soso@456:environment:asset-backup'):
            self.assertEqual(self.config(subject=subject)['subject'], subject)
        for subject in ('repo:evil/soso:ref:refs/heads/main','repo:greghogan/soso:*',
                        'repo:greghogan/soso:pull_request','repo:greghogan@123/soso:environment:prod'):
            with self.assertRaises(ValueError):
                self.config(subject=subject)

    def test_unsafe_destinations_rejected(self):
        for backup in ('s3://abc/a/../b','s3://abc/prefix*','s3://abc/a//b','s3://127.0.0.1/prefix','s3://abc/a?token=secret'):
            with self.assertRaises(ValueError):
                self.config(backup=backup)

    def test_plan_is_local_and_explicit(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()) as output:
            setup.plan(self.config(), Path(folder))
            self.assertEqual(json.loads((Path(folder)/'read.json').read_text()), setup.policies(self.config())['read.json'])
            self.assertIn('PLAN ONLY', output.getvalue())
            self.assertIn('No AWS or GitHub changes', output.getvalue())
            self.assertIn('do NOT prove live OIDC', output.getvalue())

    def test_denied_is_unverified(self):
        def denied(*args):
            raise RuntimeError('secret error text must not leak')
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(setup.verify(self.config(), denied), 1)
        self.assertIn('UNVERIFIED', output.getvalue())
        self.assertNotIn('secret error', output.getvalue())
        self.assertNotIn('PASS ', output.getvalue())

    def test_exact_readback_and_limitations(self):
        c = self.config()
        p = setup.policies(c)
        replies = {
            'get-caller-identity': {'Account': c['account']},
            'get-bucket-location': {'LocationConstraint': None},
            'get-public-access-block': {'PublicAccessBlockConfiguration': dict.fromkeys(('BlockPublicAcls','IgnorePublicAcls','BlockPublicPolicy','RestrictPublicBuckets'), True)},
            'get-bucket-ownership-controls': {'OwnershipControls': {'Rules': [{'ObjectOwnership': 'BucketOwnerEnforced'}]}},
            'get-bucket-versioning': {'Status': 'Enabled'},
            'get-bucket-encryption': {'ServerSideEncryptionConfiguration': {'Rules': [{'ApplyServerSideEncryptionByDefault': {'SSEAlgorithm':'AES256'}}]}},
            'get-open-id-connect-provider': {'Url':setup.ISSUER,'ClientIDList':['sts.amazonaws.com']},
            'get-role': {'Role': {'AssumeRolePolicyDocument':p['trust.json']}},
            'list-attached-role-policies': {'AttachedPolicies': []},
            'list-role-policies': {'PolicyNames': [setup.POLICY_NAME]},
            'get-role-policy': {'PolicyDocument':p['read.json']},
        }
        def run(*args):
            return replies[args[1]]
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(setup.verify(c, run), 0)
        self.assertIn('UNVERIFIED: actual GitHub OIDC', output.getvalue())
        replies['list-attached-role-policies'] = {'AttachedPolicies': [{'PolicyArn':'arn:aws:iam::aws:policy/AdministratorAccess'}]}
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(setup.verify(c, run), 1)


class BucketSetupTests(unittest.TestCase):
    config = AssetSetupTests.config

    def setUp(self):
        terminal = patch.object(setup.sys.stdin, "isatty", return_value=True)
        terminal.start()
        self.addCleanup(terminal.stop)
    def runner(self, overrides=None):
        replies = {
            'get-caller-identity': {'Account': '123456789012'},
            'head-bucket': setup.AWSCommandError('NoSuchBucket'),
            'get-bucket-location': {'LocationConstraint': None},
            'get-public-access-block': {'PublicAccessBlockConfiguration': dict.fromkeys(('BlockPublicAcls','IgnorePublicAcls','BlockPublicPolicy','RestrictPublicBuckets'), True)},
            'get-bucket-ownership-controls': {'OwnershipControls': {'Rules': [{'ObjectOwnership': 'BucketOwnerEnforced'}]}},
            'get-bucket-encryption': {'ServerSideEncryptionConfiguration': {'Rules': [{'ApplyServerSideEncryptionByDefault': {'SSEAlgorithm':'AES256'}}]}},
            'get-bucket-versioning': {},
            'get-bucket-lifecycle-configuration': setup.AWSCommandError('NoSuchLifecycleConfiguration'),
            'list-objects-v2': {'KeyCount': 0, 'IsTruncated': False},
            'list-object-versions': {'IsTruncated': False},
        }
        replies.update(overrides or {})
        calls = []
        def run(*args):
            calls.append(args)
            reply = replies.get(args[1], {})
            if isinstance(reply, Exception):
                raise reply
            return reply
        return run, calls

    def test_create_default_off_and_region_exception(self):
        run, calls = self.runner()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(setup.bucket_setup(self.config(), 'create', run=run, confirm=lambda _: 'create soso-private'), 0)
        creation = next(c for c in calls if c[1] == 'create-bucket')
        self.assertNotIn('--create-bucket-configuration', creation)
        self.assertNotIn('put-bucket-versioning', [c[1] for c in calls])
        self.assertIn('put-public-access-block', [c[1] for c in calls])
        run, calls = self.runner({'get-bucket-location': {'LocationConstraint':'eu-west-1'}})
        with contextlib.redirect_stdout(io.StringIO()):
            setup.bucket_setup(self.config(region='eu-west-1'), 'create', run=run, confirm=lambda _: 'create soso-private')
        self.assertIn('LocationConstraint=eu-west-1', next(c for c in calls if c[1]=='create-bucket'))

    def test_decline_and_existing_creation_never_write(self):
        for override, approval in (({}, 'no'), ({'head-bucket': {}}, 'create soso-private'),
                                   ({'head-bucket': setup.AWSCommandError('403')}, 'create soso-private')):
            run, calls = self.runner(override)
            with contextlib.redirect_stdout(io.StringIO()):
                try:
                    setup.bucket_setup(self.config(), 'create', run=run, confirm=lambda _: approval)
                except ValueError:
                    pass
            self.assertFalse(any(c[1].startswith(('create-', 'put-')) for c in calls))

    def test_existing_never_mutates_and_prefix_boundary(self):
        run, calls = self.runner({'get-bucket-versioning': {'Status':'Enabled'}})
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(setup.bucket_setup(self.config(), 'existing', run=run), 0)
        self.assertFalse(any(c[1].startswith(('create-', 'put-')) for c in calls))
        for c in calls:
            if c[1].startswith('list-'):
                self.assertEqual(c[c.index('--prefix')+1], 'backups/')
                self.assertIn('--expected-bucket-owner', c)

    def test_bucket_summary_explains_result_and_limits(self):
        for prefix in ('', 'backups'):
            c = self.config()
            c.update(prefix=prefix, backup=c['bucket'] + ('/' + prefix if prefix else ''))
            run, _ = self.runner()
            with contextlib.redirect_stdout(io.StringIO()) as output:
                setup.bucket_setup(c, 'existing', run=run)
            text = output.getvalue()
            self.assertTrue(text.startswith('Bucket checks passed:'))
            self.assertIn('bucket root (no prefix)' if not prefix else 'prefix backups', text)
            self.assertIn('Versioning: off.', text)
            self.assertIn('Selected location is empty', text)
            self.assertIn('No bucket settings or files were changed.', text)
            self.assertIn('Not checked: access granted to other AWS accounts', text)
            self.assertIn('these bucket checks do not confirm it', text)
            self.assertNotIn('local administrator', text)
            self.assertNotIn('IAM/OIDC', text)

    def test_guided_bucket_only_does_not_invent_subject(self):
        run, calls = self.runner()
        answers = iter(['us-east-1', 'skip', '3'])
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(setup.guided_setup('soso-private/backups', Path(folder), run=run,
                             ask=lambda _:next(answers), discover=lambda _:''), 0)
            config = json.loads((Path(folder)/'storage-config.json').read_text())
            self.assertEqual(config['subject'], '')
            self.assertIsNone(config['branch'])
            self.assertFalse((Path(folder)/'trust.json').exists())
        self.assertFalse(any(c[1].startswith(('create-', 'put-')) for c in calls))

    def test_guided_auth_guidance_only_on_auth_failure(self):
        for code in ('CredentialsUnavailable', 'ExpiredToken', 'InvalidClientTokenId'):
            run, _ = self.runner({'get-caller-identity': setup.AWSCommandError(code)})
            with contextlib.redirect_stdout(io.StringIO()) as output, self.assertRaisesRegex(ValueError, 'Refresh credentials'):
                setup.guided_setup('soso-private', Path('/unused'), run=run)
            self.assertEqual(output.getvalue(), 'Checking AWS identity...\n')
        run, _ = self.runner({'get-caller-identity': setup.AWSCommandError('AccessDenied')})
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(setup.AWSCommandError):
            setup.guided_setup('soso-private', Path('/unused'), run=run)

    def test_guided_success_does_not_request_sign_in(self):
        run, _ = self.runner()
        answers = iter(['us-east-1', 'skip', '3'])
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()) as output:
            setup.guided_setup('soso-private', Path(folder), run=run,
                               ask=lambda _: next(answers), discover=lambda _: '')
        self.assertNotIn('sign in', output.getvalue().lower())
        self.assertNotIn('sso', output.getvalue().lower())

    def test_guided_new_bucket_decline_never_creates(self):
        run, calls = self.runner()
        answers = iter(['us-west-2', 'create', 'no'])
        def ask(label):
            if label.startswith('AWS region'):
                self.assertTrue(any(c[1] == 'head-bucket' for c in calls))
            return next(answers)
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(setup.guided_setup('soso-private', Path(folder), run=run, ask=ask, discover=lambda _: ''), 1)
        self.assertFalse(any(c[1].startswith(('create-', 'put-')) for c in calls))

    def test_head_404_requires_structured_absence_and_never_creates_on_denial(self):
        for location_error in ('403', '404', 'AccessDenied'):
            run, calls = self.runner({'head-bucket': setup.AWSCommandError('404'),
                                      'get-bucket-location': setup.AWSCommandError(location_error)})
            with self.assertRaises(ValueError), contextlib.redirect_stdout(io.StringIO()):
                setup.bucket_setup(self.config(), 'create', run=run, confirm=lambda _: self.fail('must not prompt'))
            self.assertFalse(any(c[1].startswith(('create-', 'put-')) for c in calls))
        run, calls = self.runner({'head-bucket': setup.AWSCommandError('404'),
                                  'get-bucket-location': setup.AWSCommandError('NoSuchBucket')})
        self.assertFalse(setup.bucket_exists(['--bucket', 'soso-private', '--expected-bucket-owner', '123456789012'], run))

    def test_head_404_existing_region_is_detected_not_reset(self):
        run, calls = self.runner({'head-bucket': setup.AWSCommandError('404'),
                                  'get-bucket-location': {'LocationConstraint': 'us-west-2'}})
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(setup.guided_setup('soso-private', Path(folder), run=run,
                                               ask=lambda _: '3', discover=lambda _: ''), 0)
            self.assertEqual(json.loads((Path(folder) / 'storage-config.json').read_text())['region'], 'us-west-2')
        self.assertFalse(any(c[1].startswith(('create-', 'put-')) for c in calls))

    def test_guided_existing_detects_region_and_checks_empty_without_region_prompt(self):
        for location, expected in ((None, 'us-east-1'), ('EU', 'eu-west-1'), ('us-west-2', 'us-west-2')):
            run, calls = self.runner({'head-bucket': {}, 'get-bucket-location': {'LocationConstraint': location}})
            prompts = []
            def ask(label):
                prompts.append(label)
                return '3'
            with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(setup.guided_setup('soso-private/backups', Path(folder), run=run, ask=ask, discover=lambda _: ''), 0)
                config = json.loads((Path(folder) / 'storage-config.json').read_text())
                self.assertEqual(config['region'], expected)
            self.assertEqual(len(prompts), 1)
            self.assertEqual(prompts[0], 'Choice [1]: ')
            self.assertTrue(any(c[1] == 'list-object-versions' for c in calls))
            head = next(c for c in calls if c[1] == 'head-bucket')
            self.assertIn('--expected-bucket-owner', head)
            self.assertFalse(any(c[1].startswith(('create-', 'put-')) for c in calls))

    def test_guided_ambiguous_bucket_allows_new_name_without_owner_claim(self):
        original, calls = self.runner()
        def run(*args):
            if args[1] == 'head-bucket' and args[args.index('--bucket') + 1] == 'soso-private':
                calls.append(args)
                raise setup.AWSCommandError('403')
            return original(*args)
        answers = iter(['soso-other', 'us-west-2', 'skip', '3'])
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()) as output:
            setup.guided_setup('soso-private/backups', Path(folder), run=run, ask=lambda _: next(answers), discover=lambda _: '')
            config = json.loads((Path(folder) / 'storage-config.json').read_text())
            self.assertEqual(config['bucket'], 'soso-other')
            self.assertEqual(config['prefix'], 'backups')
        self.assertIn('Cannot verify', output.getvalue())
        self.assertNotIn('someone else', output.getvalue())
        self.assertFalse(any(c[1].startswith(('create-', 'put-')) for c in calls))

    def test_guided_unknown_region_or_bucket_can_stop_without_configuration(self):
        for overrides in ({'head-bucket': setup.AWSCommandError('403')},
                          {'head-bucket': {}, 'get-bucket-location': {}},
                          {'head-bucket': {}, 'get-bucket-location': setup.AWSCommandError('AccessDenied')}):
            run, calls = self.runner(overrides)
            with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(setup.guided_setup('soso-private', Path(folder), run=run, ask=lambda _: '', discover=lambda _: ''), 1)
                self.assertFalse((Path(folder) / 'storage-config.json').exists())
            self.assertFalse(any(c[1].startswith(('create-', 'put-')) for c in calls))

    def test_guided_existing_nonempty_stops_before_github_or_configuration(self):
        run, calls = self.runner({'head-bucket': {}, 'list-objects-v2': {'KeyCount': 1, 'IsTruncated': False, 'Contents': [{'Key': 'x'}]}})
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, 'not empty'):
            setup.guided_setup('soso-private', Path(folder), run=run,
                               ask=lambda _: self.fail('unexpected prompt'), discover=lambda _: '')

    def test_guided_complete_plan_uses_supplied_subject(self):
        run, calls = self.runner()
        subject = 'repo:greghogan@123/soso@456:ref:refs/heads/main'
        answers = iter(['us-east-1','skip','2','greghogan/soso',subject])
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(setup.guided_setup('soso-private/backups', Path(folder), run=run,
                             ask=lambda _:next(answers), discover=lambda _:''), 0)
            trust = json.loads((Path(folder)/'trust.json').read_text())
            self.assertEqual(trust['Statement'][0]['Condition']['StringEquals'][setup.ISSUER+':sub'],subject)

    def test_guided_probe_is_local_and_never_invents_trust(self):
        run, calls = self.runner()
        answers = iter(['us-east-1', 'skip', '1', 'greghogan/soso', 'cancel'])
        prompts = []
        def ask(label):
            prompts.append(label)
            return next(answers)
        with tempfile.TemporaryDirectory() as folder, patch.object(setup, 'ROOT', Path(folder)), patch('soso.assets.asset_diagnostic_run.preflight'), patch('soso.assets.asset_diagnostic_git.publish', return_value=False), contextlib.redirect_stdout(io.StringIO()):
            setup.guided_setup('soso-private', Path(folder), run=run, ask=ask, discover=lambda _: '')
            probe = (Path(folder) / 'inspect-asset-identity.yml').read_text()
            self.assertIn("github.event_name == 'workflow_dispatch'", probe)
            self.assertIn("claims.repository !== process.env.EXPECTED_REPOSITORY", probe)
            self.assertNotIn('console.log(value)', probe)
            self.assertNotIn('uses:', probe)
            self.assertNotIn('actions/checkout', probe)
            self.assertFalse((Path(folder) / 'trust.json').exists())
            setup.prepare_oidc_probe('greghogan/soso', Path(folder))
            self.assertEqual((Path(folder) / 'inspect-asset-identity.yml').read_text(), probe)
        self.assertFalse(any('subject' in p.lower() for p in prompts))
        self.assertFalse(any(c[1].startswith(('create-', 'put-')) for c in calls))

    def test_guided_github_menu_defaults_to_local_diagnostic(self):
        run, calls = self.runner({'head-bucket': {}, 'get-bucket-location': {'LocationConstraint': 'us-west-2'}})
        answers = iter(['', 'greghogan/soso', 'cancel'])
        prompts = []
        def ask(label):
            prompts.append(label)
            return next(answers)
        with tempfile.TemporaryDirectory() as folder, patch.object(setup, 'ROOT', Path(folder)), patch('soso.assets.asset_diagnostic_run.preflight'), patch('soso.assets.asset_diagnostic_git.publish', return_value=False), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(setup.guided_setup('soso-private', Path(folder), run=run,
                             ask=ask, discover=lambda _: ''), 0)
            self.assertTrue((Path(folder) / 'inspect-asset-identity.yml').exists())
            self.assertFalse((Path(folder) / 'trust.json').exists())
        self.assertEqual(prompts[0], 'Choice [1]: ')
        for label in ('1. Set up GitHub access',
                      '2. I already have the workflow identity',
                      '3. Skip GitHub access for now'):
            self.assertIn(label, output.getvalue())
        self.assertIn('Nothing is pushed or run without your approval', output.getvalue())
        self.assertNotIn('choose verified', output.getvalue())
        self.assertFalse(any(c[1].startswith(('create-', 'put-')) for c in calls))

    def test_existing_probe_passes_observed_subject_to_iam_setup(self):
        subject = 'repo:greghogan/soso:ref:refs/heads/main'
        run, calls = self.runner({'head-bucket': {}, 'get-bucket-location': {'LocationConstraint': 'us-west-2'}})
        with tempfile.TemporaryDirectory() as folder, patch.object(setup, 'ROOT', Path(folder)), patch('soso.assets.asset_diagnostic_run.preflight'), patch('soso.assets.asset_diagnostic_git.publish', return_value='commit'), patch('soso.assets.asset_diagnostic_run.run', return_value=subject) as execute, patch('soso.assets.asset_iam_setup.configure', return_value=True) as configure, contextlib.redirect_stdout(io.StringIO()) as output:
            path = Path(folder)
            setup.prepare_oidc_probe('greghogan/soso', path)
            original = (path / 'inspect-asset-identity.yml').read_text()
            answers = iter(['1', 'greghogan/soso'])
            setup.guided_setup('soso-private', path, run=run, ask=lambda _: next(answers), discover=lambda _: '')
            self.assertEqual(execute.call_args.args, ('greghogan/soso', 'commit'))
            execute.call_args.kwargs['on_dispatch'](42)
            self.assertEqual(setup.load_storage_config(path)['diagnostic']['id'], 42)
            self.assertEqual((path / 'inspect-asset-identity.yml').read_text(), original)
            self.assertFalse((path / '.github/workflows/inspect-asset-identity.yml').exists())
            self.assertEqual(configure.call_count, 1)
            self.assertEqual(configure.call_args.args[0]['subject'], subject)
            self.assertTrue(configure.call_args.args[0]['initialized'])
            self.assertFalse((path / 'trust.json').exists())
            text = output.getvalue()
            self.assertIn('Reusing diagnostic for greghogan/soso', text)
            self.assertNotIn('Enter the exact OIDC subject', text)
        self.assertFalse(any(c[1].startswith(('create-', 'put-')) for c in calls))

    def test_local_check_leaves_identical_file_and_refuses_conflicts(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            probe = setup.prepare_oidc_probe('greghogan/soso', root / 'assets/setup')
            target = root / '.github/workflows/inspect-asset-identity.yml'
            setup.check_local_oidc_probe(probe, root)
            self.assertFalse(target.exists())
            target.parent.mkdir(parents=True)
            target.write_bytes(probe.read_bytes())
            setup.check_local_oidc_probe(probe, root)
            self.assertEqual(target.read_bytes(), probe.read_bytes())
            target.write_text('different')
            with self.assertRaisesRegex(ValueError, 'not overwritten'):
                setup.check_local_oidc_probe(probe, root)
            self.assertEqual(target.read_text(), 'different')
            target.unlink()
            target.symlink_to(probe)
            with self.assertRaisesRegex(ValueError, 'unsafe'):
                setup.check_local_oidc_probe(probe, root)

    def test_dry_run_previews_missing_bucket_and_identity_without_writes(self):
        run, calls = self.runner()
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()) as output:
            path = Path(folder) / 'not-created'
            answers = iter(['us-east-1', 'create', '1', 'greghogan/soso'])
            with patch.object(setup, 'prepare_oidc_probe') as prepare, patch.object(setup, 'guide_oidc_probe') as dispatch:
                self.assertEqual(setup.guided_setup('soso-private', path, run=run, dry_run=True,
                                  ask=lambda _: next(answers), discover=lambda _: ''), 0)
                prepare.assert_not_called()
                dispatch.assert_not_called()
            self.assertIn('would create private bucket', output.getvalue())
            self.assertIn('identity for greghogan/soso is pending', output.getvalue())
            self.assertFalse(path.exists())
        self.assertFalse(any(call[1].startswith(('create-', 'put-')) for call in calls))

    def test_fresh_check_offered_only_after_definitive_saved_run_failure(self):
        from soso.assets.asset_diagnostic_run import DiagnosticUnavailable
        saved = {**self.config(), 'subject': '', 'initialized': True, 'provider': 's3'}
        saved['diagnostic'] = setup.diagnostic_binding(saved, 42)
        for error, dry_run, expect_offer in (
                (DiagnosticUnavailable('old run failed'), False, True),
                (DiagnosticUnavailable('old run expired'), True, False),
                (ValueError('GitHub authentication failed'), False, False)):
            with self.subTest(error=error, dry_run=dry_run), tempfile.TemporaryDirectory() as folder:
                output = Path(folder)
                setup.save_storage_config(saved, output)
                original = (output / 'storage-config.json').read_bytes()
                answers = iter(['', ''])
                with patch('soso.assets.asset_diagnostic_run.recover', side_effect=error), \
                     patch.object(setup, 'check_local_oidc_probe'), \
                     patch.object(setup, 'guide_oidc_probe', return_value=None) as offer, \
                     contextlib.redirect_stdout(io.StringIO()) as displayed:
                    if isinstance(error, DiagnosticUnavailable):
                        self.assertEqual(setup.github_access(saved, output, ask=lambda _: next(answers),
                                         discover=lambda _: '', dry_run=dry_run), 0)
                    else:
                        with self.assertRaisesRegex(ValueError, 'no retry was attempted'):
                            setup.github_access(saved, output, ask=lambda _: next(answers), discover=lambda _: '')
                    self.assertEqual(offer.called, expect_offer)
                    self.assertNotIn('4. Start', displayed.getvalue())
                self.assertEqual((output / 'storage-config.json').read_bytes(), original)

    def test_saved_run_resumes_without_redispatch(self):
        subject = 'repo:greghogan/soso:ref:refs/heads/main'
        run, _ = self.runner({'head-bucket': {}, 'get-bucket-location': {'LocationConstraint': 'us-east-1'}})
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            output = Path(folder)
            saved = {**self.config(), 'subject': '', 'initialized': True, 'provider': 's3'}
            saved['diagnostic'] = setup.diagnostic_binding(saved, 42)
            with patch('soso.assets.asset_diagnostic_run.recover', return_value=subject) as recover, \
                 patch.object(setup, 'guide_oidc_probe') as dispatch, \
                 patch('soso.assets.asset_iam_setup.configure'):
                answers = iter(['', ''])
                setup.guided_setup(saved['backup'], output, run=run, ask=lambda _: next(answers),
                                   discover=lambda _: '', saved=saved)
                recover.assert_called_once_with('greghogan/soso', 42, setup.oidc_probe_template('greghogan/soso').encode())
                dispatch.assert_not_called()
            self.assertEqual(setup.load_storage_config(output)['diagnostic']['id'], 42)
            for change in ({'backup': 'another-bucket'}, {'repo': 'owner/elsewhere', 'subject': ''},
                           {'account': '999999999999'}, {'region': 'us-west-2'}):
                self.assertNotIn('diagnostic', setup.validate_storage_config({**saved, **change}))

    def test_probe_mismatch_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            path = Path(folder)
            setup.prepare_oidc_probe('other/repository', path)
            original = (path / 'inspect-asset-identity.yml').read_text()
            with self.assertRaisesRegex(ValueError, 'differs from the current template'):
                setup.prepare_oidc_probe('greghogan/soso', path)
            self.assertEqual((path / 'inspect-asset-identity.yml').read_text(), original)

    def test_guided_github_invalid_choice_does_not_prepare_access(self):
        run, calls = self.runner({'head-bucket': {}, 'get-bucket-location': {'LocationConstraint': 'us-west-2'}})
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError, 'Choose 1, 2, or 3'):
                setup.guided_setup('soso-private', Path(folder), run=run,
                                   ask=lambda _: '4', discover=lambda _: '')
            self.assertFalse((Path(folder) / 'inspect-asset-identity.yml').exists())
            self.assertFalse((Path(folder) / 'trust.json').exists())
        self.assertFalse(any(c[1].startswith(('create-', 'put-')) for c in calls))

    def test_saved_adopted_destination_allows_contents_but_rechecks_settings(self):
        saved = {**self.config(), 'provider': 's3', 'initialized': True}
        for initialized in (True, False):
            run, calls = self.runner({'head-bucket': {}, 'get-bucket-location': {'LocationConstraint': None},
                                      'list-objects-v2': {'KeyCount': 1, 'IsTruncated': False, 'Contents': [{'Key': 'prior'}]}})
            with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()) as output:
                if initialized:
                    self.assertEqual(setup.guided_setup(saved['backup'], Path(folder), run=run,
                                     ask=lambda _: '3', discover=lambda _: '', saved=saved), 0)
                    self.assertIn('contents may be present', output.getvalue())
                    self.assertFalse(any(c[1].startswith('list-object') for c in calls))
                    self.assertTrue(any(c[1] == 'get-public-access-block' for c in calls))
                else:
                    with self.assertRaisesRegex(ValueError, 'not empty'):
                        setup.guided_setup(saved['backup'], Path(folder), run=run,
                                           ask=lambda _: '3', discover=lambda _: '', saved={**saved, 'initialized': False})
            self.assertFalse(any(c[1].startswith(('create-', 'put-')) for c in calls))

    def test_saved_account_mismatch_stops_before_bucket_checks(self):
        run, calls = self.runner()
        saved = {**self.config(), 'account': '999999999999', 'initialized': True}
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, 'account does not match'):
            setup.guided_setup(saved['backup'], Path('/unused'), run=run, saved=saved)
        self.assertEqual([c[1] for c in calls], ['get-caller-identity'])

    def test_canonical_saved_config_excludes_secrets_and_ignores_legacy(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            saved = {**self.config(), 'provider': 's3', 'initialized': True, 'secret': 'must-not-save'}
            setup.save_storage_config(saved, output)
            self.assertNotIn('secret', (output / 'storage-config.json').read_text())
            self.assertTrue(setup.load_storage_config(output)['initialized'])
            (output / 'storage-config.json').unlink()
            (output / 'bucket-config.json').write_text(json.dumps(saved))
            self.assertIsNone(setup.load_storage_config(output))
            (output / 'storage-config.json').write_text('{"provider":"unknown"}')
            with self.assertRaises(ValueError): setup.load_storage_config(output)

    def test_github_existing_config_detection_is_read_only_and_not_live_claim(self):
        c = self.config()
        entries = [{'name': k, 'value': v} for k, v in {
            'SOSO_ASSET_BACKUP': c['backup'], 'SOSO_AWS_REGION': c['region'],
            'SOSO_AWS_ROLE_ARN': 'arn:aws:iam::123456789012:role/soso-asset-read'}.items()]
        with patch.object(setup, 'verify', return_value=0) as verify, contextlib.redirect_stdout(io.StringIO()) as output:
            setup.detect_github_access(c, run=lambda *a: None, discover=lambda _: json.dumps(entries))
        self.assertIn('VERIFIED: GitHub repository variables match', output.getvalue())
        self.assertIn('not a live GitHub access test', output.getvalue())
        verify.assert_called_once()
        for raw in ('', '[]', '{}'):
            with patch.object(setup, 'verify', return_value=1), contextlib.redirect_stdout(io.StringIO()) as output:
                setup.detect_github_access(c, discover=lambda _: raw)
            self.assertIn('UNVERIFIED:', output.getvalue())

    def test_saved_github_values_are_enter_defaults(self):
        c = {**self.config(), 'initialized': True}
        answers = iter(['2', '', ''])
        prompts = []
        def ask(label):
            prompts.append(label)
            return next(answers)
        with tempfile.TemporaryDirectory() as folder, patch.object(setup, 'detect_github_access'), contextlib.redirect_stdout(io.StringIO()):
            setup.github_access(c, Path(folder), ask=ask, discover=lambda _: '')
            saved = setup.load_storage_config(Path(folder))
        self.assertEqual(prompts[0], 'Choice [1]: ')
        self.assertIn('[greghogan/soso]', prompts[1])
        self.assertIn('[' + c['subject'] + ']', prompts[2])
        self.assertEqual(saved['subject'], c['subject'])
        self.assertTrue(saved['initialized'])

    def test_configured_github_rerun_finishes_without_recreating_plan(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(setup, 'detect_github_access', return_value=True), patch.object(setup, 'plan') as plan, contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(setup.github_access(self.config(), Path(folder), ask=lambda _: self.fail('configured setup should finish')), 0)
            plan.assert_not_called()
            self.assertIn('already matches', out.getvalue())
            self.assertIn('does not download objects', out.getvalue())
            self.assertNotIn('create-bucket', out.getvalue())

    def test_checked_bucket_plan_omits_bucket_recreation_and_uses_uv(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()) as out:
            setup.plan(self.config(), Path(folder), bucket_ready=True)
        self.assertNotIn('create-bucket', out.getvalue())
        self.assertNotIn('python3 ', out.getvalue())
        self.assertIn('uv run --locked', out.getvalue())

    def test_default_setup_state_is_repo_anchored(self):
        self.assertEqual(setup.DEFAULT_OUTPUT, Path(setup.__file__).resolve().parents[2] / 'assets/setup')
        with tempfile.TemporaryDirectory() as folder, patch.object(setup, 'setup_storage', return_value=0) as wizard:
            import os
            previous = os.getcwd()
            try:
                os.chdir(folder)
                setup.main([])
            finally:
                os.chdir(previous)
            wizard.assert_called_once_with(setup.DEFAULT_OUTPUT, dry_run=False)

    def load_workflow(self, filename):
        # GitHub uses "on" as a string key. BaseLoader doesn't reinterpret it as boolean.
        return yaml.load((setup.ROOT / '.github/workflows' / filename).read_text(), Loader=yaml.BaseLoader)

    def assert_workflow_gate(self, job, *conditions):
        expression = job['if'].strip().removeprefix('${{').removesuffix('}}')
        terms = [re.sub(r'\s+', '', term) for term in expression.split('&&')]
        self.assertCountEqual(terms, conditions)

    def assert_workflow_credentials_scoped(self, job, reader_command):
        self.assertEqual(job['permissions']['id-token'], 'write')
        steps = job['steps']
        auth, = [step for step in steps if step.get('uses', '').partition('@')[0]
                 == 'aws-actions/configure-aws-credentials']
        reader, = [step for step in steps if reader_command in step.get('run', '')]
        self.assertLess(steps.index(auth), steps.index(reader))
        settings = auth['with']
        self.assertEqual(settings['output-env-credentials'], 'false')
        self.assertEqual(settings['output-credentials'], 'true')
        self.assertIn('vars.SOSO_AWS_ROLE_ARN', settings['role-to-assume'])
        for key in ('AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN'):
            self.assertNotIn(key, job.get('env', {}))
            for step in steps:
                if step is reader:
                    self.assertIn(f'steps.{auth["id"]}.outputs.', step['env'][key])
                else:
                    self.assertNotIn(key, step.get('env', {}))
        self.assertIn('vars.SOSO_ASSET_BACKUP', reader['env']['SOSO_ASSET_BACKUP'])
        return reader

    def test_only_trusted_pages_build_can_read_private_storage(self):
        workflow = self.load_workflow('pages.yml')
        self.assertEqual(set(workflow['on']), {'push', 'pull_request', 'workflow_dispatch'})
        self.assertEqual(workflow['on']['push']['branches'], ['main'])
        self.assertNotEqual(workflow.get('permissions', {}).get('id-token'), 'write')
        build = workflow['jobs']['build']
        self.assert_workflow_gate(build, "github.ref=='refs/heads/main'", "github.event_name!='pull_request'")
        reader = self.assert_workflow_credentials_scoped(build, 'scripts/asset_fetch.py --ci-backup')
        steps = build['steps']
        build_step, = [step for step in steps if './build.sh' in step.get('run', '')]
        self.assertLess(steps.index(reader), steps.index(build_step))
        for name, job in workflow['jobs'].items():
            for step in job.get('steps', []):
                self.assertNotIn('--public-only', step.get('run', ''))
                self.assertNotIn('actions/cache/save', step.get('uses', ''))
                if name != 'build':
                    self.assertNotIn('aws-actions/configure-aws-credentials', step.get('uses', ''))
                    self.assertNotIn('SOSO_ASSET_BACKUP', step.get('env', {}))
        pr = workflow['jobs']['pull-request']
        self.assertNotEqual(pr.get('permissions', {}).get('id-token'), 'write')
        self.assertTrue(any('./test.sh' in step.get('run', '') for step in pr['steps']))

    def test_backup_workflow_checks_metadata_without_restore(self):
        workflow = self.load_workflow('verify-asset-backup.yml')
        self.assertEqual(set(workflow['on']), {'workflow_dispatch'})
        self.assertNotEqual(workflow.get('permissions', {}).get('id-token'), 'write')
        job = workflow['jobs']['verify']
        self.assert_workflow_gate(job, "github.ref=='refs/heads/main'")
        self.assert_workflow_credentials_scoped(job, 'python -m soso.assets.asset_sync_ci')
        for step in job['steps']:
            self.assertNotIn('asset_fetch.py', step.get('run', ''))
            self.assertNotIn('./build.sh', step.get('run', ''))

    def test_noninteractive_create_rejected(self):
        run, calls = self.runner()
        with patch.object(setup.sys.stdin, 'isatty', return_value=False), self.assertRaises(ValueError):
            setup.bucket_setup(self.config(), 'create', run=run)
        self.assertFalse(any(c[1].startswith(('create-', 'put-')) for c in calls))

    def test_partial_create_failure_does_not_rollback(self):
        run, calls = self.runner({'put-bucket-encryption': setup.AWSCommandError('AccessDenied')})
        with contextlib.redirect_stdout(io.StringIO()) as output, self.assertRaises(setup.AWSCommandError):
            setup.bucket_setup(self.config(), 'create', run=run, confirm=lambda _: 'create soso-private')
        self.assertIn('may now exist', output.getvalue())
        self.assertFalse(any(c[1].startswith('delete-') for c in calls))

    def test_nonempty_denied_malformed_historical_fail(self):
        overrides = [
            {'list-objects-v2': {'KeyCount':1,'IsTruncated':False,'Contents':[{'Key':'backups/x'}]}},
            {'list-objects-v2': {}},
            {'list-object-versions': {}},
            {'get-bucket-lifecycle-configuration': {}},
            {'list-objects-v2': setup.AWSCommandError('AccessDenied')},
            {'list-object-versions': setup.AWSCommandError('AccessDenied')},
            {'list-object-versions': {'IsTruncated':False,'DeleteMarkers':[{'Key':'backups/x'}]}},
            {'get-bucket-lifecycle-configuration': {'Rules':[{'Status':'Enabled','Expiration':{'Days':30}}]}},
            {'get-caller-identity': {'Account':'000000000000'}},
        ]
        for override in overrides:
            run, calls = self.runner(override)
            with self.assertRaises((ValueError, setup.AWSCommandError)):
                setup.bucket_setup(self.config(), 'existing', run=run)
            self.assertFalse(any(c[1].startswith(('create-', 'put-')) for c in calls))


if __name__ == '__main__':
    unittest.main()
