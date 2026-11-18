"""Provider selection never contacts a cloud service in these tests."""
import unittest
import argparse
import contextlib
import io
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from soso.assets import asset_setup as setup


class SetupDispatchTests(unittest.TestCase):
    def setUp(self):
        self.terminal = patch.object(setup.sys.stdin, 'isatty', return_value=True)
        self.saved = patch.object(setup, 'load_storage_config', return_value=None)
        self.saved.start()
        self.addCleanup(self.saved.stop)
        self.terminal.start()
        self.addCleanup(self.terminal.stop)

    def test_s3_prompts_service_then_destination(self):
        ask = Mock(side_effect=['1', 'private-assets', 'originals'])
        with patch.object(setup, 'guided_setup', return_value=0) as wizard:
            self.assertEqual(setup.setup_storage(ask=ask), 0)
        wizard.assert_called_once_with('private-assets/originals', setup.DEFAULT_OUTPUT, ask=ask)
        self.assertIn('Storage service', ask.call_args_list[0].args[0])
        self.assertIn('bucket', ask.call_args_list[1].args[0])

    def test_saved_destination_is_offered_as_editable_defaults(self):
        saved = dict(provider='s3', bucket='private-assets', prefix='originals')
        for prefix_input, expected in [('', 'private-assets/originals'), ('-', 'private-assets')]:
            with patch.object(setup, 'load_storage_config', return_value=saved), patch.object(setup, 'guided_setup', return_value=0) as wizard:
                ask = Mock(side_effect=['', '', prefix_input])
                setup.setup_storage(ask=ask)
                wizard.assert_called_once_with(expected, setup.DEFAULT_OUTPUT, ask=ask, saved=saved)
                self.assertIn('[1]', ask.call_args_list[0].args[0])
                self.assertIn('[private-assets]', ask.call_args_list[1].args[0])
                self.assertIn('[originals]', ask.call_args_list[2].args[0])

    def test_saved_s3_file_provides_visible_default_and_enter_selection(self):
        # Exercise the actual canonical state loader.
        self.saved.stop()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            legacy = setup.configuration(argparse.Namespace(
                backup='private-assets', account='123456789012', repo='local/storage',
                region='us-west-2', role='soso-asset-read', subject=''), require_subject=False)
            setup.save_storage_config({**legacy, 'provider': 's3'}, output)
            ask = Mock(side_effect=['', '', ''])
            captured = io.StringIO()
            with patch.object(setup, 'guided_setup', return_value=0) as wizard, contextlib.redirect_stdout(captured):
                setup.setup_storage(output=output, ask=ask)
            self.assertIn('1. Amazon S3 (saved default; press Enter)', captured.getvalue())
            self.assertEqual(ask.call_args_list[0].args[0], 'Storage service (Enter keeps default) [1]: ')
            self.assertIn('[bucket root (no prefix)]', ask.call_args_list[2].args[0])
            self.assertEqual(wizard.call_args.args[0], 'private-assets')
            self.assertEqual(wizard.call_args.kwargs['saved']['provider'], 's3')
            self.assertFalse(wizard.call_args.kwargs['saved']['initialized'])

    def test_saved_service_is_prefilled_and_can_be_edited(self):
        from soso.assets import asset_prompts
        editor = Mock(return_value='2')
        with patch.object(setup, 'load_storage_config', return_value={'provider': 's3'}), \
                patch.object(asset_prompts, '_editor', return_value=editor), \
                patch.object(setup, 'provider_module') as module:
            ask = Mock(side_effect=AssertionError('plain input should not be called'))
            setup.setup_storage(ask=ask)
        editor.assert_called_once_with('Storage service: ', default='1', history=None,
                                       enable_history_search=False)
        module.assert_called_once_with('gcs')
        self.assertNotIn('saved', module.return_value.guided_setup.call_args.kwargs)

    def test_switching_provider_does_not_reuse_other_provider_state(self):
        with patch.object(setup, 'load_storage_config', return_value={'provider': 's3'}), patch.object(setup, 'provider_module') as module:
            setup.setup_storage(ask=Mock(return_value='2'))
            self.assertNotIn('saved', module.return_value.guided_setup.call_args.kwargs)

    def test_other_provider_owns_destination_prompts(self):
        for choice, provider in [('2', 'gcs'), ('3', 'azure')]:
            with self.subTest(provider=provider), patch.object(setup, 'provider_module') as module:
                module.return_value.guided_setup.return_value = 0
                ask = Mock(return_value=choice)
                self.assertEqual(setup.setup_storage(ask=ask), 0)
                module.assert_called_once_with(provider)
                module.return_value.guided_setup.assert_called_once_with(output=setup.DEFAULT_OUTPUT, ask=ask)

    def test_s3compatible_dispatch(self):
        for choice, provider in (('4', 'r2'), ('5', 'b2')):
            with self.subTest(provider=provider), patch.object(setup, 'provider_module') as module:
                ask = Mock(return_value=choice)
                setup.setup_storage(ask=ask)
                module.assert_called_once_with('s3compatible')
                module.return_value.guided_setup.assert_called_once_with(
                    provider=provider, output=setup.DEFAULT_OUTPUT, ask=ask)

    def test_noninteractive_rejected(self):
        with patch.object(setup.sys.stdin, 'isatty', return_value=False), self.assertRaisesRegex(ValueError, 'interactive terminal'):
            setup.setup_storage()

    def test_setup_and_dry_run_start_the_same_wizard(self):
        for argv, dry_run in (([], False), (['--dry-run'], True)):
            with self.subTest(argv=argv), patch.object(setup, 'setup_storage', return_value=0) as wizard:
                setup.main(argv)
                wizard.assert_called_once_with(setup.DEFAULT_OUTPUT, dry_run=dry_run)

    def test_provider_and_destination_flags_are_rejected(self):
        for argv in (['--provider', 'azure'], ['--destination', 's3://assets/prefix']):
            with self.subTest(argv=argv), patch.object(setup, 'setup_storage') as wizard, contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    setup.main(argv)
                self.assertEqual(error.exception.code, 2)
                wizard.assert_not_called()


if __name__ == '__main__':
    unittest.main()
