import unittest
from unittest.mock import Mock, patch
from soso.assets import asset_prompts as p


class PromptTests(unittest.TestCase):
    def test_fallback_keeps_and_clears(self):
        for answer, expected in [('', 'saved'), ('-', ''), ('other', 'other')]:
            ask = Mock(return_value=answer)
            self.assertEqual(p.text(ask, 'Prefix', 'saved', allow_clear=True), expected)
            self.assertIn('Enter keeps default', ask.call_args.args[0])

    def test_edited_empty_is_not_replaced(self):
        editor = Mock(return_value='')
        with patch.object(p, '_editor', return_value=editor):
            self.assertEqual(p.text(input, 'Prefix', 'saved'), '')
        self.assertEqual(editor.call_args.args[0], 'Prefix: ')
        self.assertEqual(editor.call_args.kwargs['default'], 'saved')
        self.assertIsNone(editor.call_args.kwargs['history'])

    def test_editor_interrupt_propagates(self):
        with patch.object(p, '_editor', return_value=Mock(side_effect=EOFError)), self.assertRaises(EOFError):
            p.text(input, 'Prefix', 'saved')

    def test_editor_accept_edit_clear_and_empty(self):
        from prompt_toolkit import prompt
        from prompt_toolkit.application import create_app_session
        from prompt_toolkit.input import create_pipe_input
        from prompt_toolkit.output import DummyOutput

        cases = [
            ('saved', b'\r', 'saved'),
            ('saved', b'-edited\r', 'saved-edited'),
            ('saved', b'\x01\x0b\r', ''),  # Ctrl-A, Ctrl-K, Enter
            ('', b'\r', ''),
        ]
        for default, keystrokes, expected in cases:
            with self.subTest(default=default, keystrokes=keystrokes), create_pipe_input() as pipe:
                pipe.send_bytes(keystrokes)
                with create_app_session(input=pipe, output=DummyOutput()), patch.object(p, '_editor', return_value=prompt):
                    self.assertEqual(p.text(input, 'Prefix', default, allow_clear=True), expected)
