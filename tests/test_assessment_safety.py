import os
import unittest
from unittest.mock import patch

from services import assessment_safety


class AssessmentSafetyTests(unittest.TestCase):
    def test_missing_engine_flag_defaults_to_legacy(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(assessment_safety.engine_mode(), "legacy")
            self.assertEqual(assessment_safety.shadow_primary(), "legacy")

    def test_invalid_flags_fail_closed_to_legacy(self):
        with patch.dict(
            os.environ,
            {"ASSESSMENT_ENGINE": "broken", "ASSESSMENT_SHADOW_PRIMARY": "broken"},
            clear=True,
        ):
            self.assertEqual(assessment_safety.engine_mode(), "legacy")
            self.assertEqual(assessment_safety.shadow_primary(), "legacy")

    def test_v2_hard_gate_rejects_incomplete_set(self):
        questions = [
            {
                "prompt": f"Question {i}",
                "answer": "a",
                "distractors": ["b", "c", "d"],
            }
            for i in range(9)
        ]
        self.assertFalse(assessment_safety._hard_gate_pass(questions, 10))

    def test_v2_hard_gate_accepts_complete_valid_set(self):
        questions = [
            {
                "prompt": f"Question {i}",
                "answer": f"a{i}",
                "distractors": [f"b{i}", f"c{i}", f"d{i}"],
            }
            for i in range(10)
        ]
        self.assertTrue(assessment_safety._hard_gate_pass(questions, 10))


if __name__ == "__main__":
    unittest.main()
