from pathlib import Path
import html
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'shared'))
import math_notation as notation


class MathNotationTests(unittest.TestCase):
    def test_every_declared_identifier_is_explicitly_subscripted(self):
        for token, spec in notation.TOKEN_SPECS.items():
            with self.subTest(token=token):
                self.assertIn('_{', notation.token_to_latex(token))
                self.assertIn('<sub>', notation.token_to_html(token))
                self.assertIn(spec.index, notation.token_to_html(token))

    def test_descriptive_labels_upright_numeric_indices_not_roman_words(self):
        self.assertEqual(notation.token_to_latex('Tfinal'), r'\(T_{\mathrm{final}}\)')
        self.assertEqual(notation.token_to_latex('Th', inline=False), r'T_{\mathrm{h}}')
        self.assertEqual(notation.token_to_latex('V2'), r'\(V_{2}\)')
        self.assertEqual(notation.token_to_html('Rp'), '<i>R</i><sub>p</sub>')

    def test_boundaries_do_not_change_words_identifiers_or_case(self):
        unchanged = 'Theory Qheat Femitters Lfoo Tfinality MyT1 T1_extra λmaxima th rp'
        text, replacements = notation.protect_notation(unchanged, 'latex')
        self.assertEqual(text, unchanged)
        self.assertEqual(replacements, {})
        text, replacements = notation.protect_notation('(Th), Tc/Qh − Qc; V2=V1×T2/T1.', 'latex')
        self.assertEqual(len(replacements), 8)
        self.assertIn(r'\(T_{\mathrm{h}}\)', notation.restore_notation(text, replacements))

    def test_html_escaping_does_not_escape_math_markup(self):
        text, replacements = notation.protect_notation('Tfinal < Tstart & H₂O', 'html')
        result = notation.restore_notation(html.escape(text), replacements)
        self.assertEqual(result, '<i>T</i><sub>final</sub> &lt; <i>T</i><sub>start</sub> &amp; H<sub>2</sub>O')

    def test_unicode_zero_alias_and_chemical_runs(self):
        self.assertEqual(notation.token_to_latex('λ₀'), notation.token_to_latex('λ0'))
        text, replacements = notation.protect_notation('4 H₂ + CO₂ → CH₄ + 2 H₂O; C₁₂', 'latex')
        result = notation.restore_notation(text, replacements)
        self.assertEqual(result, r'4 H\textsubscript{2} + CO\textsubscript{2} → CH\textsubscript{4} + 2 H\textsubscript{2}O; C\textsubscript{12}')

    def test_optional_unicode_conversion_and_placeholder_collision(self):
        text, replacements = notation.protect_notation('ZZINDEXEDNOTATION0ZZ H₂ Qh', 'html', unicode_subscripts=False)
        self.assertIn('H₂', text)
        result = notation.restore_notation(text, replacements)
        self.assertTrue(result.startswith('ZZINDEXEDNOTATION0ZZ'))
        self.assertTrue(result.endswith('<i>Q</i><sub>h</sub>'))

    def test_complete_equation_placeholders_are_unchanged(self):
        text, replacements = notation.protect_notation('ZZPRINTMATH0ZZ and Qh', 'latex')
        self.assertIn('ZZPRINTMATH0ZZ', text)
        self.assertEqual(len(replacements), 1)

    def test_unknown_notation_is_not_guessed(self):
        text, replacements = notation.protect_notation('V3 Tother Lx', 'latex')
        self.assertEqual(text, 'V3 Tother Lx')
        self.assertFalse(replacements)
        with self.assertRaises(KeyError): notation.token_to_latex('Tother')
        with self.assertRaises(ValueError): notation.protect_notation('Th', 'svg')


if __name__ == '__main__':
    unittest.main()
