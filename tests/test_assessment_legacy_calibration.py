import types
import unittest

from services import assessment_legacy_calibration


class LegacyCandidateCalibrationTests(unittest.TestCase):
    _PROMPTS = [
        "Choose the greeting used when meeting a teacher in the morning.",
        "Select the phrase that politely asks for directions at a station.",
        "Which response accepts an invitation without sounding informal?",
        "Choose the form that agrees with a masculine singular noun.",
        "Select the expression used to order an item in a café.",
        "Which sentence correctly asks another person their name?",
        "Choose the phrase that closes a short formal conversation.",
        "Select the correct response to a question about location.",
        "Which option expresses possession with the taught structure?",
        "Choose the sentence that uses the target preposition correctly.",
        "Select the phrase that asks about opening time.",
        "Which response is appropriate when thanking a stranger?",
    ]

    def _q(self, i, level="A1"):
        return {
            "prompt": self._PROMPTS[i % len(self._PROMPTS)],
            "answer": f"answer{i}",
            "distractors": [f"choice{i}a", f"choice{i}b", f"choice{i}c"],
            "difficulty": level,
            "_objective_operation": "contextual-use",
            "_objective_target": f"skill-{i}",
        }

    def test_short_a1_vocabulary_gets_small_headroom(self):
        calls = []

        def generator(*args, **kwargs):
            count = kwargs.get("count", args[4] if len(args) > 4 else 10)
            calls.append(count)
            return [self._q(i) for i in range(count)]

        fake = types.SimpleNamespace(ai_generate_questions=generator)
        assessment_legacy_calibration.install(fake)

        result = fake.ai_generate_questions(
            topic_title="Greetings",
            topic_type="vocabulary",
            topic_content={"pages": [{"items": [{"term": f"answer{i}"} for i in range(20)]}]},
            language="Spanish",
            count=10,
            level="A1",
            existing_questions=[],
        )

        self.assertEqual(calls, [12])
        self.assertEqual(len(result), 10)

    def test_b1_grammar_does_not_oversample_long_items(self):
        calls = []

        def generator(*args, **kwargs):
            count = kwargs.get("count", args[4] if len(args) > 4 else 10)
            calls.append(count)
            rows = []
            for i in range(count):
                q = self._q(i, level="B1")
                q["_objective_operation"] = "grammar"
                rows.append(q)
            return rows

        fake = types.SimpleNamespace(ai_generate_questions=generator)
        assessment_legacy_calibration.install(fake)

        result = fake.ai_generate_questions(
            topic_title="Past perfect",
            topic_type="grammar",
            topic_content={"pages": [{"rules": ["past-before-past rule"]}]},
            language="German",
            count=10,
            level="B1",
            existing_questions=[],
        )

        self.assertEqual(calls, [10])
        self.assertEqual(len(result), 10)

    def test_genuine_grammar_form_competitors_are_not_pseudoforms(self):
        from services import assessment_legacy_filter as gate

        # install() patches the shared final gate, so use a tiny fake engine to activate it.
        fake = types.SimpleNamespace(ai_generate_questions=lambda *a, **k: [])
        assessment_legacy_calibration.install(fake)

        q = {
            "prompt": "Nachdem Herr Meyer in München _____, fuhr er ins Büro.",
            "answer": "angekommen war",
            "distractors": ["ankam", "angekommen hatte", "angekommen ist"],
            "difficulty": "B1",
            "_objective_operation": "grammar",
        }
        source = "TOPIC Plusquamperfekt (grammar)\nangekommen war angekommen hatte angekommen ist"
        headers = gate._topic_headers(source)
        reason = gate._quality_reason(
            q,
            source_text=source,
            headers=headers,
            accepted=[],
            prior=[],
            operation_counts={},
            requested=10,
        )
        self.assertIsNone(reason)

    def test_meta_letter_shape_and_symbolic_arithmetic_are_generic_failures(self):
        from services import assessment_legacy_filter as gate

        headers = gate._topic_headers("TOPIC Everyday vocabulary (vocabulary)")
        letter_q = {
            "prompt": "Which taught word starts with the letter combination 'ph'?",
            "answer": "photo",
            "distractors": ["house", "table", "book"],
        }
        arithmetic_q = {
            "prompt": "What is 12 - 5?",
            "answer": "seven",
            "distractors": ["six", "eight", "nine"],
        }

        self.assertEqual(
            assessment_legacy_calibration._extra_quality_reason(gate, letter_q, headers),
            "letter_or_spelling_trivia",
        )
        self.assertEqual(
            assessment_legacy_calibration._extra_quality_reason(gate, arithmetic_q, headers),
            "arithmetic",
        )


if __name__ == "__main__":
    unittest.main()
