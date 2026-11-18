"""The same paths serve standalone generation and isolated Docker staging."""
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from shared.build_paths import event_output


class EventOutputTests(unittest.TestCase):
    event = Path('/sandbox/project/events/solar-system-b/2027')

    def test_direct_output_is_inside_build(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(event_output(self.event),
                             Path('/sandbox/project/build/direct/events/solar-system-b/2027'))

    def test_isolated_stage_keeps_event_layout(self):
        with patch.dict(os.environ, {'SOSO_STAGE_OUTPUTS': '1'}, clear=True):
            self.assertEqual(event_output(self.event), self.event)

    def test_explicit_output_has_precedence(self):
        with patch.dict(os.environ, {'SOSO_EVENT_OUTPUT_DIR': '/sandbox/build/custom',
                                     'SOSO_STAGE_OUTPUTS': '1'}, clear=True):
            self.assertEqual(event_output(self.event), Path('/sandbox/build/custom'))
