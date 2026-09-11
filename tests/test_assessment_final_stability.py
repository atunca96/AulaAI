import types
import unittest

from services import assessment_legacy_calibration
from services import assessment_prompt_policy


class AssessmentFinalStabilityTests(unittest.TestCase):
    def test_candidate_repair_has_enough_single_pass_headroom(self):
        self.assertGreaterEqual(assessment_legacy_calibration._repair_count(10, 1), 7)
        self.assertGreaterEqual(assessment_legacy_calibration._repair_count(10, 2), 10)
        self.assertLessEqual(assessment_legacy_calibration._repair_count(10, 2), 12)

    def test_ordered_lexical_set_trivia_is_blocked_in_prompt_policy(self):
        captured = {}

        def fake_call(messages, *args, **kwargs):
            captured["messages"] = messages
            captured["kwargs"] = kwargs
            return {"questions": []}

        fake = types.SimpleNamespace(_call_ai=fake_call)
        assessment_prompt_policy.install(fake)
        fake._call_ai(
            [
                {
                    "role": "system",
                    "content": "You are Pedagogic Assessment Engine (V5)\nPEDAGOGIC PROTOCOL & MANDATES:\nold\nRESPONSE FORMAT:\njson",
                },
                {
                    "role": "user",
                    "content": "TASK: Generate EXACTLY 10 questions\nJSON STRUCTURE:\n{}",
                },
            ],
            max_tokens=4000,
            temperature=0.8,
            allow_fallback=True,
        )

        system = captured["messages"][0]["content"]
        user = captured["messages"][1]["content"]
        self.assertIn("ORDERED-SET LANGUAGE, NOT SEQUENCE TRIVIA", system)
        self.assertIn("what comes next", system)
        self.assertIn("ordered lexical sets", user)
        self.assertEqual(captured["kwargs"]["max_tokens"], 2500)
        self.assertEqual(captured["kwargs"]["temperature"], 0.30)
        self.assertFalse(captured["kwargs"]["allow_fallback"])


if __name__ == "__main__":
    unittest.main()
