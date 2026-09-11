import os
import types
import unittest
from unittest.mock import patch

from services import assessment_router_v2
from services.assessment_scorecard import build_scorecard
from services.assessment_telemetry import complete_trace, install, trace_assessment


class AssessmentObservabilityTests(unittest.TestCase):
    def test_shared_provider_timer_detects_v2_planner(self):
        module = types.SimpleNamespace()
        module._call_ai = lambda messages, *args, **kwargs: {"ok": True}
        install(module)

        with trace_assessment("v2", 10, 1, request_id="test-v2") as trace:
            module._call_ai([
                {"role": "system", "content": "You are AulaAI Assessment Planner V2."},
                {"role": "user", "content": "x"},
            ], model="test-model")
        complete_trace(trace, 10)

        self.assertEqual(trace["provider_calls"], 1)
        self.assertEqual(trace["provider_calls_by_phase"]["planner"], 1)
        self.assertIn("test-model", trace["models"])

    def test_shared_provider_timer_detects_legacy_writer(self):
        module = types.SimpleNamespace()
        module._call_ai = lambda messages, *args, **kwargs: {"ok": True}
        install(module)

        with trace_assessment("legacy", 7, 1, request_id="test-legacy") as trace:
            module._call_ai([
                {"role": "system", "content": "Pedagogic Assessment Engine (V5)"},
            ])
        complete_trace(trace, 7)

        self.assertEqual(trace["provider_calls"], 1)
        self.assertEqual(trace["provider_calls_by_phase"]["legacy_writer"], 1)

    def test_scorecard_flags_count_and_duplicate_proxies(self):
        questions = [
            {
                "prompt": "¿Cómo se escribe el número 12 en español?",
                "answer": "doce",
                "distractors": ["once", "trece", "diez"],
            },
            {
                "prompt": "¿Cómo se escribe el número 15 en español?",
                "answer": "quince",
                "distractors": ["catorce", "cinco", "trece"],
            },
        ]
        score = build_scorecard(questions, 2, source_text="doce quince once trece diez catorce cinco")
        self.assertTrue(score["requested_count_match"])
        self.assertEqual(score["valid_mcq_rate"], 1.0)
        self.assertGreater(score["objective_duplicate_proxy_rate"], 0.0)
        self.assertEqual(score["source_grounding_proxy_rate"], 1.0)

    def test_engine_flag_defaults_safely_to_v2(self):
        with patch.dict(os.environ, {"ASSESSMENT_ENGINE": "not-a-real-engine"}, clear=False):
            self.assertEqual(assessment_router_v2._engine_mode(), "v2")
        with patch.dict(os.environ, {"ASSESSMENT_ENGINE": "legacy"}, clear=False):
            self.assertEqual(assessment_router_v2._engine_mode(), "legacy")
        with patch.dict(os.environ, {"ASSESSMENT_ENGINE": "shadow"}, clear=False):
            self.assertEqual(assessment_router_v2._engine_mode(), "shadow")


if __name__ == "__main__":
    unittest.main()
