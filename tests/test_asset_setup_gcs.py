import sys
import io
from contextlib import redirect_stdout
import unittest
from unittest.mock import patch
from pathlib import Path
from soso.assets import asset_setup_gcs as gcs

class GcsSetupTests(unittest.TestCase):
    def setUp(self):
        self.c = gcs.configuration('gs://example-bucket/path', 'example-project', '123')
        self.bucket = {'name': 'example-bucket', 'projectNumber': '123', 'iamConfiguration': {
            'uniformBucketLevelAccess': {'enabled': True}, 'publicAccessPrevention': 'enforced'}}
    def test_preview_and_verify_never_write(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as temporary, patch.object(gcs, 'verify', return_value=0) as check:
            out = Path(temporary) / 'not-created'
            answers = iter(['', '', 'existing'])
            self.assertEqual(gcs.guided_setup(self.c['backup'], out, lambda _: next(answers),
                                             saved=self.c, dry_run=True), 0)
            self.assertEqual(check.call_args.kwargs, {'require_empty': True})
            self.assertFalse(out.exists())
            self.assertEqual(gcs.verify_saved(self.c), 0)
            self.assertEqual(check.call_args.kwargs, {'require_empty': False})

    def read(self, *args):
        return {'projectNumber': '123'} if args[0] == 'project' else self.bucket
    def listing(self, *args, **kwargs):
        return {'kind': 'storage#objects'}
    def test_native_metadata_and_exact_prefix(self):
        with patch.object(gcs, 'read_json', return_value={'kind':'storage#objects'}) as read:
            self.assertEqual(gcs.object_listing(self.c), {'kind':'storage#objects'})
            self.assertEqual(read.call_args.args, (
                'https://storage.googleapis.com/storage/v1/b/example-bucket/o',
                {'prefix':'path/', 'maxResults':'1', 'versions':'true'}))
            gcs.object_listing(self.c, soft_deleted=True)
            self.assertEqual(read.call_args.args[1], {'prefix':'path/', 'maxResults':'1', 'softDeleted':'true'})
            gcs.metadata('project', 'example-project')
            self.assertEqual(read.call_args.args[0], 'https://cloudresourcemanager.googleapis.com/v1/projects/example-project')
            gcs.metadata('bucket', 'example-bucket')
            self.assertEqual(read.call_args.args[0], 'https://storage.googleapis.com/storage/v1/b/example-bucket')
    def test_verified_empty(self):
        self.assertEqual(gcs.verify(self.c, self.read, self.listing), 0)
    def test_unknown_or_nonempty_listing(self):
        for data in ({}, {'kind': 'storage#objects', 'nextPageToken': 'x'}, {'kind': 'storage#objects', 'items': [{}]}):
            self.assertEqual(gcs.verify(self.c, self.read, lambda *a, **k: data), 1)
    def test_soft_deleted_blocks(self):
        self.assertEqual(gcs.verify(self.c, self.read, lambda *a, **k: {'kind':'storage#objects', 'items':[{}] if k else []}), 1)
    def test_security_controls(self):
        self.bucket['iamConfiguration']['publicAccessPrevention'] = 'inherited'
        self.assertEqual(gcs.verify(self.c, self.read, self.listing), 1)
    def test_project_mismatch(self):
        self.bucket['projectNumber'] = '999'
        self.assertEqual(gcs.verify(self.c, self.read, self.listing), 1)
    def test_lifecycle_blocks(self):
        self.bucket['lifecycle'] = {'rule': [{'action': {'type':'Delete'}}]}
        self.assertEqual(gcs.verify(self.c, self.read, self.listing), 1)
    def test_prefix_validation(self):
        for path in ('gs://example-bucket/a/../b', 'gs://example-bucket/a*'):
            with self.assertRaises(ValueError):
                gcs.configuration(path, 'example-project', '123')

class GcsRerunTests(unittest.TestCase):
    setUp = GcsSetupTests.setUp
    read = GcsSetupTests.read
    listing = GcsSetupTests.listing
    def test_known_destination_rechecks_security_without_emptiness_claim(self):
        output = io.StringIO()
        with patch.object(gcs, 'object_listing') as listing, redirect_stdout(output):
            self.assertEqual(gcs.verify(self.c, self.read, listing, require_empty=False), 0)
            listing.assert_not_called()
        self.assertIn('Emptiness was not checked', output.getvalue())
        self.bucket['iamConfiguration']['publicAccessPrevention'] = 'inherited'
        self.assertEqual(gcs.verify(self.c, self.read, self.listing, require_empty=False), 1)

    def test_saved_defaults_resume_only_after_fresh_validation(self):
        prompts = []
        answers = iter(['', '', '', '', 'y'])
        def ask(prompt):
            prompts.append(prompt)
            return next(answers)
        saved = dict(self.c, initialized=True)
        with patch.object(gcs, 'verify', return_value=0) as verify, patch.object(gcs, 'save_configuration') as save, patch.object(gcs, 'plan') as plan:
            self.assertEqual(gcs.guided_setup(ask=ask, saved=saved), 0)
            verify.assert_called_once_with(self.c, require_empty=False)
            save.assert_called_once_with(saved, Path('assets/setup'))
            plan.assert_not_called()
        self.assertIn('[example-bucket]', prompts[0])
        self.assertIn('[path]', prompts[1])
        self.assertIn('[example-project]', prompts[2])
        self.assertIn('[123]', prompts[3])

    def test_changed_prefix_or_project_requires_empty_initialization(self):
        for answers, expected in [(['', '-', '', '', '', 'y'], dict(self.c, prefix='', backup='gs://example-bucket')),
                                  (['', '', 'another-project', '', '', 'y'], dict(self.c, project='another-project'))]:
            with self.subTest(expected=expected), patch.object(gcs, 'verify', return_value=0) as verify, patch.object(gcs, 'save_configuration') as save, patch.object(gcs, 'plan'):
                self.assertEqual(gcs.guided_setup(ask=lambda _: answers.pop(0), saved=dict(self.c, initialized=True)), 0)
                verify.assert_called_once_with(expected, require_empty=True)
                save.assert_called_once_with(dict(expected, initialized=True), Path('assets/setup'))

    def test_explicit_alternate_destination_does_not_inherit_initialization(self):
        answers = iter(['', '', '', 'y'])
        with patch.object(gcs, 'verify', return_value=0) as verify, patch.object(gcs, 'save_configuration'), patch.object(gcs, 'plan'):
            self.assertEqual(gcs.guided_setup(backup='gs://another-bucket/new', ask=lambda _: next(answers), saved=dict(self.c, initialized=True)), 0)
            self.assertTrue(verify.call_args.kwargs['require_empty'])

    def test_uninitialized_saved_plan_requires_empty_validation(self):
        answers = iter(['', '', '', '', '', 'y'])
        with patch.object(gcs, 'verify', return_value=0) as verify, patch.object(gcs, 'save_configuration'), patch.object(gcs, 'plan'):
            self.assertEqual(gcs.guided_setup(ask=lambda _: next(answers), saved=dict(self.c, initialized=False)), 0)
            self.assertTrue(verify.call_args.kwargs['require_empty'])

    def test_failed_validation_does_not_save(self):
        answers = iter(['', '', '', '', 'y'])
        with patch.object(gcs, 'verify', return_value=1), patch.object(gcs, 'save_configuration') as save:
            self.assertEqual(gcs.guided_setup(ask=lambda _: next(answers), saved=dict(self.c, initialized=True)), 1)
            save.assert_not_called()

    def test_declined_known_destination_preserves_prior_initialization(self):
        answers = iter(['', '', '', '', 'n'])
        with patch.object(gcs, 'verify') as verify, patch.object(gcs, 'save_configuration') as save:
            self.assertEqual(gcs.guided_setup(ask=lambda _: next(answers), saved=dict(self.c, initialized=True)), 1)
            verify.assert_not_called()
            save.assert_called_once_with(dict(self.c, initialized=True), Path('assets/setup'))

    def test_declined_new_plan_saves_unverified_defaults(self):
        answers = iter(['example-bucket', 'path', 'example-project', '123', 'new', ''])
        with patch.object(gcs, 'verify') as verify, patch.object(gcs, 'save_configuration') as save, patch.object(gcs, 'plan'):
            self.assertEqual(gcs.guided_setup(ask=lambda _: next(answers)), 1)
            verify.assert_not_called()
            save.assert_called_once_with(dict(self.c, initialized=False), Path('assets/setup'))

    def test_declined_changed_destination_does_not_inherit_marker(self):
        answers = iter(['', '', '', 'n'])
        with patch.object(gcs, 'verify') as verify, patch.object(gcs, 'save_configuration') as save, patch.object(gcs, 'plan'):
            self.assertEqual(gcs.guided_setup(backup='gs://another-bucket/new', ask=lambda _: next(answers), saved=dict(self.c, initialized=True)), 1)
            verify.assert_not_called()
            save.assert_called_once_with(dict(self.c, bucket='another-bucket', prefix='new', backup='gs://another-bucket/new', initialized=False), Path('assets/setup'))

if __name__ == '__main__':
    unittest.main()
