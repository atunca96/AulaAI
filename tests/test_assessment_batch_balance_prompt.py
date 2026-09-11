import unittest

from services.assessment_batch_balance_prompt import install


class FakeEngine:
    def __init__(self):
        self.calls = []

    def _call_ai(self, messages, *args, **kwargs):
        self.calls.append(messages)
        return messages


class BatchBalancePromptTests(unittest.TestCase):
    def test_assessment_call_gets_balance_directive(self):
        engine = FakeEngine()
        install(engine)
        messages = [
            {"role": "system", "content": "Pedagogic Assessment Engine (V7.4 FINAL)"},
            {"role": "user", "content": "TASK: Generate EXACTLY 10 questions"},
        ]
        out = engine._call_ai(messages)
        user = out[1]["content"]
        self.assertIn("BATCH BALANCE OVERRIDE", user)
        self.assertIn("no more than two combined", user)
        self.assertIn("Never repeat the same underlying transferable target", user)

    def test_nonassessment_call_is_unchanged(self):
        engine = FakeEngine()
        install(engine)
        messages = [
            {"role": "system", "content": "Lesson material generator"},
            {"role": "user", "content": "Generate lesson content"},
        ]
        out = engine._call_ai(messages)
        self.assertEqual(out, messages)


if __name__ == "__main__":
    unittest.main()
