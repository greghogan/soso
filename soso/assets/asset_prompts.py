"""Editable nonsecret setup fields; menus and confirmations stay explicit."""
import builtins
import sys


def _editor(ask):
    if ask is not builtins.input or not sys.stdin.isatty() or not sys.stdout.isatty():
        return None
    try:
        from prompt_toolkit import prompt
    except ImportError:
        return None
    return prompt


def text(ask, label, default='', *, empty_label='empty', allow_clear=False):
    """Return edited contents, including deliberately empty input.

    No persistent history is configured, and no readline hooks are modified.
    Without an editable terminal, explicitly distinguish keeping from clearing.
    """
    editor = _editor(ask)
    if editor is not None:
        return editor(label + ': ', default=default, history=None,
                      enable_history_search=False).strip()
    shown = default or empty_label
    hint = 'Enter keeps default'
    if allow_clear:
        hint += '; - for ' + empty_label
    value = ask(f'{label} ({hint}) [{shown}]: ').strip()
    return '' if allow_clear and value == '-' else value or default
