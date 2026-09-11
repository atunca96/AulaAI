import types
import unittest

from services import assessment_prompt_policy


class AssessmentPromptPolicyV72Tests(unittest.TestCase):
    def test_assessment_call_gets_v72_coverage_plan_without_runtime_slowdown(self):
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
        self.assertIn("Pedagogic Assessment Engine (V7.2)", system)
        self.assertIn("BATCH COVERAGE MAP", system)
        self.assertIn("different supported families before revisiting one", user)
        self.assertEqual(captured["kwargs"]["max_tokens"], 2500)
        self.assertEqual(captured["kwargs"]["temperature"], 0.30)
        self.assertFalse(captured["kwargs"]["allow_fallback"])

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
