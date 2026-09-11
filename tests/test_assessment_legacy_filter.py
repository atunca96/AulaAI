import types
import unittest

from services import assessment_legacy_filter


class LegacyQualityGateTests(unittest.TestCase):
    def _clean(self, i):
        return {
            "id": f"q{i}",
            "topic_id": 1,
            "type": "mcq",
            "prompt": f"Choose the correct classroom response for situation {i}.",
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

    def test_filters_meta_and_refills_to_requested_count_before_persist(self):
        calls = []
        persisted = []

        def legacy(**kwargs):
            calls.append(dict(kwargs))
            if len(calls) == 1:
                return [self._clean(i) for i in range(8)] + [self._meta(8), self._meta(9)]
            return [self._clean(100 + i) for i in range(kwargs["count"])]

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
        self.assertEqual(calls[0]["count"], 10)
        self.assertTrue(all(call["is_quiz"] is False for call in calls))
        self.assertFalse(any("fonet" in q["prompt"].lower() for q in result))

    def test_preserves_dynamic_requested_count(self):
        calls = []

        def legacy(**kwargs):
            calls.append(dict(kwargs))
            if len(calls) == 1:
                return [self._clean(i) for i in range(14)] + [self._meta(14)]
            return [self._clean(200 + i) for i in range(kwargs["count"])]

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

    def test_rejects_live_cross_language_and_morphology_trivia(self):
        cross = {
            "prompt": "¿Qué característica ortográfica distingue a cuatro respecto a otras lenguas romances?",
            "answer": "Se escribe con cu en lugar de qu",
            "distractors": ["Lleva tilde", "Empieza con k", "Termina con e"],
            "difficulty": "A1",
        }
        morph = {
            "prompt": "¿Cuál es el prefijo de enlace característico de los números 21 al 29?",
            "answer": "veinti-",
            "distractors": ["treinti-", "veinte y", "dieciy-"],
            "difficulty": "A1",
        }
        headers = assessment_legacy_filter._topic_headers("TOPIC Numbers (vocabulary)")
        for q, expected in ((cross, "cross_language_trivia"), (morph, "morphology_terminology")):
            reason = assessment_legacy_filter._quality_reason(
                q, source_text="TOPIC Numbers (vocabulary)", headers=headers,
                accepted=[], prior=[], operation_counts={}, requested=10,
            )
            self.assertEqual(reason, expected)

    def test_rejects_live_pseudoform_distractors(self):
        q = {
            "prompt": "¿Cómo se escribe de forma correcta el número que sigue al siete?",
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
