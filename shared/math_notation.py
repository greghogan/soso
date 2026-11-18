"""Small, explicit notation vocabulary for the manual renderers.

This is NOT a mathematical-expression parser. Complete equations should be
rendered by their authored equation representation first. Call protect_notation
on remaining *prose text*, escape the returned text for the output format, then
restore_notation. Do not run it over URLs, already-rendered HTML/TeX, or raw JSON.

Descriptive indices (hot/cold, planet/star, final, etc.) are upright labels;
numerical indices are naturally upright. The base variable remains italic in
both outputs. Unicode digit subscripts are positioned explicitly rather than
relying on a font's compatibility-glyph design.
"""
from __future__ import annotations

from html import escape
import re
from types import MappingProxyType
from typing import NamedTuple


class Identifier(NamedTuple):
    base: str
    latex_base: str
    index: str
    kind: str = 'label'  # label, number, or variable


TOKEN_SPECS = MappingProxyType({
    'λobserved': Identifier('λ', r'\lambda', 'observed'),
    'λmax': Identifier('λ', r'\lambda', 'max'),
    'ηmax': Identifier('η', r'\eta', 'max'),
    'Femit': Identifier('F', 'F', 'emit'),
    'Fgrav': Identifier('F', 'F', 'grav'),
    'Pabs': Identifier('P', 'P', 'abs'),
    'Rp': Identifier('R', 'R', 'p'),
    'Rstar': Identifier('R', 'R', 'star'),
    'Th': Identifier('T', 'T', 'h'),
    'Tc': Identifier('T', 'T', 'c'),
    'Qh': Identifier('Q', 'Q', 'h'),
    'Qc': Identifier('Q', 'Q', 'c'),
    'Lf': Identifier('L', 'L', 'f'),
    'V1': Identifier('V', 'V', '1', 'number'),
    'V2': Identifier('V', 'V', '2', 'number'),
    'T1': Identifier('T', 'T', '1', 'number'),
    'T2': Identifier('T', 'T', '2', 'number'),
    'Tobject': Identifier('T', 'T', 'object'),
    'Tsurroundings': Identifier('T', 'T', 'surroundings'),
    'Tfinal': Identifier('T', 'T', 'final'),
    'Tstart': Identifier('T', 'T', 'start'),
    'Tpredicted': Identifier('T', 'T', 'predicted'),
    'λ₀': Identifier('λ', r'\lambda', '0', 'number'),
    'λ0': Identifier('λ', r'\lambda', '0', 'number'),
})

_SUB_DIGITS = '₀₁₂₃₄₅₆₇₈₉'
_SUB_TRANSLATION = str.maketrans(_SUB_DIGITS, '0123456789')
_IDENTIFIERS = '(?<!\\w)(?:' + '|'.join(
    re.escape(t) for t in sorted(TOKEN_SPECS, key=len, reverse=True)
) + ')(?!\\w)'
_IDENTIFIER_PATTERN = re.compile(_IDENTIFIERS)
_ALL_PATTERN = re.compile(_IDENTIFIERS + '|[' + _SUB_DIGITS + ']+')


def token_to_latex(token: str, *, inline: bool = True) -> str:
    """Typeset an exact known identifier; raise KeyError for an unknown token."""
    spec = TOKEN_SPECS[token]
    index = r'\mathrm{' + spec.index + '}' if spec.kind == 'label' else spec.index
    result = spec.latex_base + '_{' + index + '}'
    return r'\(' + result + r'\)' if inline else result


def token_to_html(token: str) -> str:
    """Return semantic inline math with an explicitly positioned subscript."""
    spec = TOKEN_SPECS[token]
    index = escape(spec.index)
    if spec.kind == 'variable':
        index = '<i>' + index + '</i>'
    return '<i>' + escape(spec.base) + '</i><sub>' + index + '</sub>'


def protect_notation(text: str, target: str, *, unicode_subscripts: bool = True
                     ) -> tuple[str, dict[str, str]]:
    """Protect known identifiers before ordinary TeX/HTML escaping.

    Example::

        protected, replacements = protect_notation('Tfinal & H₂O', 'latex')
        escaped = ordinary_prose_tex_escape(protected)
        result = restore_notation(escaped, replacements)

    Existing full-equation placeholders are left untouched. Unknown notation is
    left untouched too: the vocabulary is deliberate, not heuristic guessing.
    """
    if target not in ('latex', 'html'):
        raise ValueError("target must be 'latex' or 'html'")
    text = str(text)
    prefix = 'ZZINDEXEDNOTATION'
    while prefix in text:
        prefix += 'X'
    replacements: dict[str, str] = {}

    def replace(match: re.Match[str]) -> str:
        token = match.group()
        if token in TOKEN_SPECS:
            rendered = token_to_latex(token) if target == 'latex' else token_to_html(token)
        else:
            digits = token.translate(_SUB_TRANSLATION)
            rendered = (r'\textsubscript{' + digits + '}' if target == 'latex'
                        else '<sub>' + digits + '</sub>')
        marker = prefix + str(len(replacements)) + 'ZZ'
        replacements[marker] = rendered
        return marker

    pattern = _ALL_PATTERN if unicode_subscripts else _IDENTIFIER_PATTERN
    return pattern.sub(replace, text), replacements


def restore_notation(text: str, replacements: dict[str, str]) -> str:
    """Restore markup only after ordinary output-format escaping has finished."""
    for marker, rendered in replacements.items():
        text = text.replace(marker, rendered)
    return text
