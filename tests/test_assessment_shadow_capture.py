import os
import unittest
from unittest.mock import patch

from services import assessment_shadow_capture


class FakeRouter:
    def __init__(self):
        self.calls = []

        def run_engine(engine, **kwargs):
            self.calls.append((engine, kwargs))
            return ([{
                "prompt": "Pregunta de prueba",
                "answer": "uno",
                "distractors": ["dos", "tres", "cuatro"],
                "translation_en": "ignored",
            }], {"engine": engine})

        self._run_engine = run_engine
        self._assessment_shadow_capture_installed = False


class AssessmentShadowCaptureTests(unittest.TestCase):
    def test_disabled_by_default(self):
        router = FakeRouter()
        assessment_shadow_capture.install(router)
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(assessment_shadow_capture, "_emit") as emit:
                router._run_engine("v2", shadow=True, request_id="r1")
        emit.assert_not_called()

    def test_only_v2_shadow_is_captured(self):
        router = FakeRouter()
        assessment_shadow_capture.install(router)
        with patch.dict(os.environ, {"ASSESSMENT_SHADOW_CAPTURE": "1"}, clear=False):
            with patch.object(assessment_shadow_capture, "_emit") as emit:
                router._run_engine("legacy", shadow=True, request_id="r1")
                router._run_engine("v2", shadow=False, request_id="r2")
                emit.assert_not_called()
                router._run_engine("v2", shadow=True, request_id="r3")
        emit.assert_called_once()
        args = emit.call_args.args
        self.assertEqual(args[0], "r3")
        self.assertEqual(args[1], "v2")

    def test_capture_view_excludes_source_and_translations(self):
        question = {
            "prompt": "Pregunta",
            "answer": "uno",
            "distractors": ["dos", "tres", "cuatro"],
            "translation_en": "translation",
            "why": "reason",
            "source": "secret source text",
        }
        view = assessment_shadow_capture._question_view(question)
        self.assertEqual(set(view.keys()), {"prompt", "answer", "distractors"})
        self.assertNotIn("source", view)
        self.assertNotIn("translation_en", view)
        self.assertNotIn("why", view)


if __name__ == "__main__":
    unittest.main()
