import unittest
from unittest.mock import patch

from services import assessment_engine_v2_validated as validated


class ValidatedAssessmentEngineTests(unittest.TestCase):
    def test_rejected_objective_is_refilled_before_writer(self):
        first_plan = [
            {
                "id": "o1", "key": "uno-use", "topic_id": "1", "skill": "grammar use",
                "target": "Use un before masculine singular nouns",
                "evidence": "uno changes to un before masculine singular nouns", "question_mode": "form-choice",
            },
            {
                "id": "o2", "key": "bad-etymology", "topic_id": "1", "skill": "historical knowledge",
                "target": "Identify the etymological origin of cinco",
                "evidence": "cinco derives historically from Latin quinque", "question_mode": "meaning",
            },
            {
                "id": "o3", "key": "dos-use", "topic_id": "1", "skill": "contextual use",
                "target": "Use dos naturally when ordering two coffees",
                "evidence": "dos is used for two coffees", "question_mode": "situational",
            },
        ]
        refill = [
            {
                "id": "o1", "key": "zero-temperature", "topic_id": "1", "skill": "contextual use",
                "target": "Use cero to express zero temperature",
                "evidence": "cero is used for zero degrees", "question_mode": "completion",
            }
        ]

        topic_sources = {
            "1": {
                "title": "Numbers", "type": "vocabulary",
                "text": (
                    "uno changes to un before masculine singular nouns. "
                    "cinco derives historically from Latin quinque. "
                    "dos is used for two coffees. cero is used for zero degrees."
                ),
            }
        }

        def fake_writer(language, level, objectives, evidence, previous, history, accepted):
            made = []
            for obj in objectives:
                made.append({
                    "objective_id": obj["id"], "objective_key": obj["key"], "topic_id": obj["topic_id"],
                    "type": "mcq", "prompt": f"Question for {obj['key']}?",
                    "translation_en": "Question?", "translation_tr": "Soru?",
                    "answer": f"answer-{obj['id']}",
                    "distractors": [f"a-{obj['id']}", f"b-{obj['id']}", f"c-{obj['id']}"],
                    "why": "Because.", "why_tr": "Çünkü.",
                })
            return made, []

        topics = [{"id": 1, "title": "Numbers", "type": "vocabulary", "content": {}}]
        with patch.object(validated, "_topic_evidence_bundle", return_value=(topic_sources["1"]["text"], topic_sources)), \
             patch.object(validated.base, "_plan_objectives", side_effect=[first_plan, refill]) as planner, \
             patch.object(validated.base, "_generate_for_objectives", side_effect=fake_writer), \
             patch.object(validated.base, "_get_history", return_value=[]), \
             patch.object(validated.base, "_remember"), \
             patch.object(validated, "_annotate_validation") as annotate:
            result = validated.generate_assessment_questions(
                topics=topics, language="Spanish", level="A1", count=3, previous_questions=[]
            )

        self.assertEqual(len(result), 3)
        self.assertEqual(planner.call_count, 2)
        summary = annotate.call_args.args[0]
        self.assertTrue(summary["accepted_count_match"])
        self.assertEqual(summary["rejected_objective_count"], 1)
        self.assertEqual(summary["reason_counts"].get("etymology"), 1)


if __name__ == "__main__":
    unittest.main()
