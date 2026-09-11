import types
import unittest

from services import assessment_legacy_filter


class LegacyMetaFilterTests(unittest.TestCase):
    def _clean(self, i):
        return {
            "id": f"q{i}",
            "topic_id": 1,
            "type": "mcq",
            "prompt": f"Mesa para {i}, por favor.",
            "answer": str(i),
            "distractors": [f"a{i}", f"b{i}", f"c{i}"],
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
        self.assertEqual(calls[1]["count"], 4)
        self.assertTrue(all(call["is_quiz"] is False for call in calls))
        self.assertFalse(any("fonet" in q["prompt"].lower() for q in result))
        self.assertGreaterEqual(len(calls[1]["existing_questions"]), 10)

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
        )
        assessment_legacy_filter.install(router)

        result = router._LEGACY_GENERATOR(
            topic_ids=[1], count=15, is_quiz=False, ui_lang="en",
            existing_questions=[], progress_callback=None,
        )
        self.assertEqual(len(result), 15)
        self.assertEqual(calls[0]["count"], 15)
        self.assertEqual(calls[1]["count"], 4)

    def test_no_refill_when_initial_batch_is_clean(self):
        calls = []

        def legacy(**kwargs):
            calls.append(dict(kwargs))
            return [self._clean(i) for i in range(kwargs["count"])]

        router = types.SimpleNamespace(
            _LEGACY_GENERATOR=legacy,
            _persist_primary_questions=lambda qs: None,
        )
        assessment_legacy_filter.install(router)

        result = router._LEGACY_GENERATOR(
            topic_ids=[1], count=7, is_quiz=False, ui_lang="en",
            existing_questions=[], progress_callback=None,
        )
        self.assertEqual(len(result), 7)
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
