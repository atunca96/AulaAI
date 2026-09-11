import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from services import assessment_safety


class AssessmentSafetyTests(unittest.TestCase):
    def _questions(self, count):
        return [
            {
                "id": f"q{i}",
                "topic_id": 1,
                "prompt": f"Question {i}",
                "answer": f"a{i}",
                "distractors": [f"b{i}", f"c{i}", f"d{i}"],
            }
            for i in range(count)
        ]

    def test_missing_engine_flag_defaults_to_legacy(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(assessment_safety.engine_mode(), "legacy")
            self.assertEqual(assessment_safety.shadow_primary(), "legacy")

    def test_invalid_flags_fail_closed_to_legacy(self):
        with patch.dict(
            os.environ,
            {"ASSESSMENT_ENGINE": "broken", "ASSESSMENT_SHADOW_PRIMARY": "broken"},
            clear=True,
        ):
            self.assertEqual(assessment_safety.engine_mode(), "legacy")
            self.assertEqual(assessment_safety.shadow_primary(), "legacy")

    def test_v2_hard_gate_rejects_incomplete_set(self):
        self.assertFalse(assessment_safety._hard_gate_pass(self._questions(9), 10))

    def test_v2_hard_gate_accepts_complete_valid_set(self):
        self.assertTrue(assessment_safety._hard_gate_pass(self._questions(10), 10))

    def test_shadow_v2_primary_falls_back_before_persisting_incomplete_result(self):
        v2_result = self._questions(9)
        legacy_result = self._questions(10)
        routed_calls = []
        persisted = []
        legacy_calls = []

        def routed_generate(**kwargs):
            routed_calls.append(kwargs)
            return v2_result

        def run_engine(engine, **kwargs):
            legacy_calls.append((engine, kwargs))
            self.assertEqual(engine, "legacy")
            return legacy_result, {}

        router = SimpleNamespace(
            _engine_mode=lambda: "legacy",
            _shadow_primary=lambda: "legacy",
            _source_text=lambda topic_ids: "",
            _run_engine=run_engine,
            _persist_primary_questions=lambda questions: persisted.append(questions),
        )
        content = SimpleNamespace(generate_assessment_set=routed_generate)
        assessment_safety.install(router, content)

        with patch.dict(
            os.environ,
            {"ASSESSMENT_ENGINE": "shadow", "ASSESSMENT_SHADOW_PRIMARY": "v2"},
            clear=True,
        ):
            result = content.generate_assessment_set([1], count=10, is_quiz=True)

        self.assertEqual(result, legacy_result)
        self.assertEqual(routed_calls[0]["is_quiz"], False)
        self.assertEqual(len(legacy_calls), 1)
        self.assertEqual(persisted, [legacy_result])
        self.assertNotIn(v2_result, persisted)

    def test_shadow_v2_primary_persists_only_after_hard_gate_passes(self):
        v2_result = self._questions(10)
        routed_calls = []
        persisted = []

        def routed_generate(**kwargs):
            routed_calls.append(kwargs)
            return v2_result

        router = SimpleNamespace(
            _engine_mode=lambda: "legacy",
            _shadow_primary=lambda: "legacy",
            _source_text=lambda topic_ids: "",
            _run_engine=lambda *args, **kwargs: self.fail("legacy fallback should not run"),
            _persist_primary_questions=lambda questions: persisted.append(questions),
        )
        content = SimpleNamespace(generate_assessment_set=routed_generate)
        assessment_safety.install(router, content)

        with patch.dict(
            os.environ,
            {"ASSESSMENT_ENGINE": "shadow", "ASSESSMENT_SHADOW_PRIMARY": "v2"},
            clear=True,
        ):
            result = content.generate_assessment_set([1], count=10, is_quiz=True)

        self.assertEqual(result, v2_result)
        self.assertEqual(routed_calls[0]["is_quiz"], False)
        self.assertEqual(persisted, [v2_result])


if __name__ == "__main__":
    unittest.main()
