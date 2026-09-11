import types
import unittest

from services import assessment_legacy_filter


class LegacyQualityGateTests(unittest.TestCase):
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
        "Which option completes the classroom request naturally?",
        "Choose the phrase that asks for a price politely.",
        "Select the correct reply to a yes or no question.",
        "Which expression identifies a family relationship correctly?",
        "Choose the form that marks the taught grammatical contrast.",
        "Select the sentence that uses the target verb in context.",
        "Which reply indicates that the speaker does not understand?",
        "Choose the polite expression for requesting repetition.",
        "Select the phrase that gives a simple destination.",
        "Which sentence uses the taught article correctly?",
        "Choose the expression that introduces another person.",
        "Select the response that indicates agreement.",
        "Which option asks about quantity using the taught form?",
        "Choose the phrase that describes a simple daily routine.",
        "Select the correct form for a direct classroom instruction.",
        "Which response answers the taught time question naturally?",
    ]

    def _clean(self, i):
        prompt = self._PROMPTS[i % len(self._PROMPTS)]
        return {
            "id": f"q{i}",
            "topic_id": 1,
            "type": "mcq",
            "prompt": prompt,
            "answer": f"answer{i}",
            "distractors": [f"option{i}a", f"option{i}b", f"option{i}c"],
            "difficulty": "A1",
        }

    def _meta(self, i):
        return {
            "id": f"m{i}",
            "topic_id": 1,
            "type": "mcq",
            "prompt": "¿Qué rasgo fonético contiene este diptongo?",
            "answer": "ei",
            "distractors": ["a", "b", "c"],
            "difficulty": "A1",
        }

    def test_filters_meta_and_uses_at_most_one_outer_refill(self):
        calls = []
        persisted = []

        def legacy(**kwargs):
            calls.append(dict(kwargs))
            if len(calls) == 1:
                return [self._clean(i) for i in range(8)] + [self._meta(8), self._meta(9)]
            return [self._clean(20 + i) for i in range(kwargs["count"])]

        router = types.SimpleNamespace(
            _LEGACY_GENERATOR=legacy,
            _persist_primary_questions=lambda qs: persisted.extend(qs),
            _source_text=lambda ids: "",
        )
        assessment_legacy_filter.install(router)

        result = router._LEGACY_GENERATOR(
            topic_ids=[1], count=10, is_quiz=True, ui_lang="en",
            existing_questions=[], progress_callback=None,
        )

        self.assertEqual(len(result), 10)
        self.assertEqual(len(persisted), 10)
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(call["is_quiz"] is False for call in calls))
        self.assertFalse(any("fonet" in q["prompt"].lower() for q in result))

    def test_preserves_dynamic_requested_count(self):
        calls = []

        def legacy(**kwargs):
            calls.append(dict(kwargs))
            if len(calls) == 1:
                return [self._clean(i) for i in range(14)] + [self._meta(14)]
            return [self._clean(20 + i) for i in range(kwargs["count"])]

        router = types.SimpleNamespace(
            _LEGACY_GENERATOR=legacy,
            _persist_primary_questions=lambda qs: None,
            _source_text=lambda ids: "",
        )
        assessment_legacy_filter.install(router)

        result = router._LEGACY_GENERATOR(
            topic_ids=[1], count=15, is_quiz=False, ui_lang="en",
            existing_questions=[], progress_callback=None,
        )
        self.assertEqual(len(result), 15)
        self.assertEqual(calls[0]["count"], 15)
        self.assertLessEqual(len(calls), 2)

    def test_no_refill_when_initial_batch_is_clean(self):
        calls = []

        def legacy(**kwargs):
            calls.append(dict(kwargs))
            return [self._clean(i) for i in range(kwargs["count"])]

        router = types.SimpleNamespace(
            _LEGACY_GENERATOR=legacy,
            _persist_primary_questions=lambda qs: None,
            _source_text=lambda ids: "",
        )
        assessment_legacy_filter.install(router)

        result = router._LEGACY_GENERATOR(
            topic_ids=[1], count=7, is_quiz=False, ui_lang="en",
            existing_questions=[], progress_callback=None,
        )
        self.assertEqual(len(result), 7)
        self.assertEqual(len(calls), 1)

    def test_rejects_cross_language_and_morphology_trivia(self):
        cases = [
            ({
                "prompt": "¿Qué característica ortográfica distingue a cuatro respecto a otras lenguas romances?",
                "answer": "Se escribe con cu en lugar de qu",
                "distractors": ["Lleva tilde", "Empieza con k", "Termina con e"],
                "difficulty": "A1",
            }, "cross_language_trivia"),
            ({
                "prompt": "¿Cuál es el prefijo de enlace característico de los números 21 al 29?",
                "answer": "veinti-",
                "distractors": ["treinti-", "veinte y", "dieciy-"],
                "difficulty": "A1",
            }, "morphology_terminology"),
            ({
                "prompt": "¿Cuál pertenece al grupo de raíces irregulares únicas?",
                "answer": "doce",
                "distractors": ["diecisiete", "veintidós", "treinta"],
                "difficulty": "A1",
            }, "morphology_terminology"),
        ]
        headers = assessment_legacy_filter._topic_headers("TOPIC Numbers (vocabulary)")
        for q, expected in cases:
            reason = assessment_legacy_filter._quality_reason(
                q, source_text="TOPIC Numbers (vocabulary)", headers=headers,
                accepted=[], prior=[], operation_counts={}, requested=10,
            )
            self.assertEqual(reason, expected)

    def test_rejects_single_word_pseudoform_distractors(self):
        q = {
            "prompt": "Selecciona la forma enseñada para esta situación.",
            "answer": "ocho",
            "distractors": ["otto", "ohto", "otxo"],
            "difficulty": "A1",
        }
        reason = assessment_legacy_filter._quality_reason(
            q,
            source_text="TOPIC Numbers (vocabulary)\nocho siete nueve diez",
            headers="topic numbers vocabulary",
            accepted=[], prior=[], operation_counts={}, requested=10,
        )
        self.assertEqual(reason, "pseudoform_distractors")

    def test_rejects_multiword_glued_pseudoforms(self):
        q = {
            "prompt": "Selecciona la forma correcta enseñada para esta cantidad.",
            "answer": "treinta y uno",
            "distractors": ["treintiuno", "treintauno", "treintayuno"],
            "difficulty": "A1",
        }
        reason = assessment_legacy_filter._quality_reason(
            q,
            source_text="TOPIC Numbers (vocabulary)\ntreinta y uno",
            headers="topic numbers vocabulary",
            accepted=[], prior=[], operation_counts={}, requested=10,
        )
        self.assertEqual(reason, "pseudoform_distractors")

    def test_rejects_normalization_duplicate_options(self):
        q = {
            "prompt": "Queremos ____ cafés con leche.",
            "answer": "dos",
            "distractors": ["doz", "dós", "duo"],
            "difficulty": "A1",
        }
        reason = assessment_legacy_filter._quality_reason(
            q,
            source_text="TOPIC Numbers (vocabulary)\ndos tres cuatro",
            headers="topic numbers vocabulary",
            accepted=[], prior=[], operation_counts={}, requested=10,
        )
        self.assertEqual(reason, "invalid_mcq_structure")

    def test_rejects_parenthesized_numeric_answer_leak(self):
        q = {
            "prompt": "El billete cuesta ____ (6) euros.",
            "answer": "seis",
            "distractors": ["cinco", "siete", "ocho"],
            "difficulty": "A1",
        }
        reason = assessment_legacy_filter._quality_reason(
            q,
            source_text="TOPIC Numbers (vocabulary)\nseis cinco siete ocho",
            headers="topic numbers vocabulary",
            accepted=[], prior=[], operation_counts={}, requested=10,
        )
        self.assertEqual(reason, "answer_revealed")

    def test_rejects_direct_digit_to_word_giveaway(self):
        q = {
            "prompt": "¿Qué palabra indica la cantidad 3?",
            "answer": "tres",
            "distractors": ["cinco", "siete", "nueve"],
            "difficulty": "A1",
        }
        reason = assessment_legacy_filter._quality_reason(
            q,
            source_text="TOPIC Numbers (vocabulary)\ntres cinco siete nueve",
            headers="topic numbers vocabulary",
            accepted=[], prior=[], operation_counts={}, requested=10,
        )
        self.assertEqual(reason, "answer_revealed")

    def test_limits_blank_completion_overconcentration(self):
        counts = {"blank_completion": 3}
        q = {
            "prompt": "Mesa para ____, por favor.",
            "answer": "uno",
            "distractors": ["dos", "tres", "cuatro"],
            "difficulty": "A1",
        }
        reason = assessment_legacy_filter._quality_reason(
            q,
            source_text="TOPIC Numbers (vocabulary)\nuno dos tres cuatro mesa para",
            headers="topic numbers vocabulary",
            accepted=[], prior=[], operation_counts=counts, requested=10,
        )
        self.assertEqual(reason, "operation_overconcentration")

    def test_allows_meta_when_topic_is_explicitly_central(self):
        q = {
            "prompt": "¿Cuál de estas palabras lleva tilde?",
            "answer": "camión",
            "distractors": ["casa", "mesa", "libro"],
            "difficulty": "B1",
        }
        reason = assessment_legacy_filter._quality_reason(
            q,
            source_text="TOPIC Accentuation (orthography)\ncamión casa mesa libro",
            headers="topic accentuation orthography",
            accepted=[], prior=[], operation_counts={}, requested=10,
        )
        self.assertIsNone(reason)


if __name__ == "__main__":
    unittest.main()
