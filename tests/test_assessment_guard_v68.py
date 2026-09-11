import types
import unittest

from services import assessment_guard


class AssessmentGuardV68Tests(unittest.TestCase):
    def setUp(self):
        assessment_guard._TOPIC_HISTORY.clear()

    def _q(self, i, operation="contextual-use", target=None):
        target = target or f"distinct-target-{i}"
        token = f"token{i}"
        return {
            "prompt": f"Use {token} in a distinct learner situation.",
            "answer": f"answer-{token}",
            "distractors": [f"d{i}a", f"d{i}b", f"d{i}c"],
            "why": f"[[OBJ:{operation}:{target}]] grounded explanation",
            "why_tr": "açıklama",
        }

    def _meta(self, kind, i):
        if kind == "phonology":
            prompt = "¿Qué rasgo fonético contiene este diptongo?"
        else:
            prompt = "¿Cuál de estos números se escribe con tilde?"
        q = self._q(i, operation="pronunciation" if kind == "phonology" else "orthography-form")
        q["prompt"] = prompt
        return q

    def test_meta_is_rejected_inside_guard_and_one_small_repair_restores_count(self):
        calls = []

        def original(*args, **kwargs):
            calls.append(dict(kwargs))
            if len(calls) == 1:
                return [self._q(i) for i in range(8)] + [
                    self._meta("phonology", 8),
                    self._meta("tilde", 9),
                ]
            requested = int(kwargs.get("count", 0) or 0)
            return [self._q(100 + i, operation="meaning") for i in range(requested)]

        module = types.SimpleNamespace(
            ai_generate_questions=original,
            _semantic_diversity_guard_installed=False,
        )
        assessment_guard.install(module)

        result = module.ai_generate_questions(
            topic_title="Any topic",
            topic_type="vocabulary",
            topic_content={},
            language="Spanish",
            count=10,
            level="A1",
            existing_questions=[],
        )

        self.assertEqual(len(result), 10)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1]["count"], 4)
        self.assertFalse(any("fonet" in q["prompt"].lower() for q in result))
        self.assertFalse(any("tilde" in q["prompt"].lower() for q in result))

    def test_same_operation_and_near_underlying_target_is_one_objective(self):
        first = assessment_guard._prepare_question({
            "prompt": "First scenario",
            "answer": "x",
            "why": "[[OBJ:contextual-use:select cardinal number in everyday context]] one",
        })
        second = assessment_guard._prepare_question({
            "prompt": "Completely different scenario",
            "answer": "y",
            "why": "[[OBJ:contextual-use:choose cardinal number in an everyday context]] two",
        })
        self.assertTrue(assessment_guard._objective_same(first, second))

    def test_public_question_does_not_leak_internal_objective_metadata(self):
        prepared = assessment_guard._prepare_question({
            "prompt": "Prompt",
            "answer": "Answer",
            "why": "[[OBJ:grammar:masculine singular apocope]] explanation",
        })
        public = assessment_guard._public_question(prepared)
        self.assertNotIn("_objective_key", public)
        self.assertNotIn("_objective_operation", public)
        self.assertNotIn("_objective_target", public)
        self.assertEqual(public["why"], "explanation")


if __name__ == "__main__":
    unittest.main()
