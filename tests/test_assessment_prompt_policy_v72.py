import types
import unittest

from services import assessment_prompt_policy


class AssessmentPromptPolicyV74Tests(unittest.TestCase):
    def _assessment_call(self):
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
        return captured

    def test_assessment_call_gets_v74_final_quality_without_runtime_slowdown(self):
        captured = self._assessment_call()
        system = captured["messages"][0]["content"]
        user = captured["messages"][1]["content"]

        self.assertIn("Pedagogic Assessment Engine (V7.4 FINAL)", system)
        self.assertIn("UNIVERSAL QUALITY RUBRIC", system)
        self.assertIn("DISTRACTOR SOPHISTICATION", system)
        self.assertIn("BLIND-OPTION CHECK", system)
        self.assertIn("THREE-MISCONCEPTION CHECK", system)
        self.assertIn("All THREE distractors", system)
        self.assertIn("realistic CEFR-appropriate learner errors", user)
        self.assertIn("blind-option check", user)
        self.assertEqual(captured["kwargs"]["max_tokens"], 2500)
        self.assertEqual(captured["kwargs"]["temperature"], 0.30)
        self.assertFalse(captured["kwargs"]["allow_fallback"])

    def test_task_types_and_cefr_still_apply(self):
        captured = self._assessment_call()
        system = captured["messages"][0]["content"]
        for marker in (
            "GRAMMAR:",
            "SPEAKING:",
            "VOCABULARY:",
            "CULTURE:",
            "FUNCTIONAL LANGUAGE:",
            "CEFR SCALING A1–C2",
        ):
            self.assertIn(marker, system)

    def test_culture_is_source_locked_not_globally_banned(self):
        captured = self._assessment_call()
        system = captured["messages"][0]["content"]
        self.assertIn("Culture questions may test source-taught cultural knowledge", system)
        self.assertIn("Avoid stereotypes, unsupported generalizations and obscure trivia", system)

    def test_non_assessment_call_is_untouched(self):
        captured = {}

        def fake_call(messages, *args, **kwargs):
            captured["messages"] = messages
            captured["kwargs"] = kwargs
            return {"ok": True}

        fake = types.SimpleNamespace(_call_ai=fake_call)
        assessment_prompt_policy.install(fake)

        original_messages = [
            {"role": "system", "content": "Lesson material generator"},
            {"role": "user", "content": "Generate a lesson"},
        ]
        fake._call_ai(original_messages, max_tokens=6000, temperature=0.7, allow_fallback=True)

        self.assertEqual(captured["messages"], original_messages)
        self.assertEqual(captured["kwargs"]["max_tokens"], 6000)
        self.assertEqual(captured["kwargs"]["temperature"], 0.7)
        self.assertTrue(captured["kwargs"]["allow_fallback"])


if __name__ == "__main__":
    unittest.main()
