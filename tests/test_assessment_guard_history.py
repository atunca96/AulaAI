import unittest

from services import assessment_guard as guard


class AssessmentGuardHistoryTests(unittest.TestCase):
    def _q(self, prompt, answer, key):
        return {
            "prompt": prompt,
            "answer": answer,
            "distractors": ["x", "y", "z"],
            "why": f"[[OBJ:{key}]] short reason",
        }

    def test_prior_same_objective_new_example_is_allowed(self):
        prior = [
            self._q(
                "Nachdem Herr Meyer angekommen war, fuhr er ins Büro.",
                "angekommen war",
                "grammar:plusquamperfekt-auxiliary-selection",
            )
        ]
        candidate = self._q(
            "Der Zug war bereits abgefahren, als Lukas anrief. Welche Form ist korrekt?",
            "war abgefahren",
            "grammar:plusquamperfekt-auxiliary-selection",
        )

        result = guard.dedupe_questions([candidate], prior=prior, limit=1)
        self.assertEqual(len(result), 1)

    def test_prior_near_copy_is_still_blocked(self):
        prior = [
            self._q(
                "Nachdem Herr Meyer in München angekommen war, fuhr er direkt ins Büro.",
                "angekommen war",
                "grammar:plusquamperfekt-arrival",
            )
        ]
        candidate = self._q(
            "Nachdem Herr Meyer in München angekommen war, fuhr er direkt ins Büro.",
            "angekommen war",
            "grammar:plusquamperfekt-arrival",
        )

        result = guard.dedupe_questions([candidate], prior=prior, limit=1)
        self.assertEqual(result, [])

    def test_same_objective_inside_current_batch_is_blocked(self):
        q1 = self._q(
            "Nachdem wir gegessen hatten, gingen wir los.",
            "hatten gegessen",
            "grammar:plusquamperfekt-before-past",
        )
        q2 = self._q(
            "Nachdem sie gelernt hatte, schrieb sie die Prüfung.",
            "hatte gelernt",
            "grammar:plusquamperfekt-before-past",
        )

        result = guard.dedupe_questions([q1, q2], prior=[], limit=2)
        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()
