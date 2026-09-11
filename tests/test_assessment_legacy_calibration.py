import types
import unittest

from services import assessment_legacy_calibration


class LegacyCandidateCalibrationTests(unittest.TestCase):
    _PROMPTS = [
        "Choose the greeting used when meeting a teacher in the morning.",
        "Select the phrase that politely asks for directions at a station.",
        "Which response accepts an invitation without sounding informal?",
        "Choose the form that agrees with a masculine singular noun.",
        "Select the expression used to order one item in a café.",
        "Which sentence correctly asks another person their name?",
        "Choose the phrase that closes a short formal conversation.",
        "Select the correct response to a question about location.",
        "Which option expresses possession with the taught structure?",
        "Choose the sentence that uses the target preposition correctly.",
        "Select the phrase that asks about opening time.",
        "Which response is appropriate when thanking a stranger?",
        "Choose the form used before a plural noun in this lesson.",
        "Select the sentence that correctly negates the taught expression.",
    ]

    def _q(self, i):
        return {
            "prompt": self._PROMPTS[i % len(self._PROMPTS)],
            "answer": f"answer{i}",
            "distractors": [f"choice{i}a", f"choice{i}b", f"choice{i}c"],
            "difficulty": "A1",
        }

    def test_oversamples_once_and_returns_requested_count(self):
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

    def test_extra_guard_catches_letter_shape_and_arithmetic_trivia(self):
        from services import assessment_legacy_filter as gate

        headers = gate._topic_headers("TOPIC Numbers (vocabulary)")
        letter_q = {
            "prompt": "¿Qué número se escribe con 'cu' inicial en español?",
            "answer": "cuatro",
            "distractors": ["cinco", "cero", "seis"],
        }
        arithmetic_q = {
            "prompt": "¿Cómo se escribe el número formado por diez más siete?",
            "answer": "diecisiete",
            "distractors": ["dieciocho", "diecinueve", "veinte"],
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
