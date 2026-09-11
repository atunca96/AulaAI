import unittest
from unittest.mock import patch

from services import assessment_engine_v2_validated as validated


class ValidatedAssessmentEngineTests(unittest.TestCase):
    def _all_questions_valid(self, questions, objectives_by_id, topic_sources, level):
        return list(questions), [], {
            "validator_version": "question_validator_v1",
            "input_count": len(questions),
            "accepted_count": len(questions),
            "rejected_count": 0,
            "accept_rate": 1.0,
            "reason_counts": {},
        }

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
             patch.object(validated, "validate_questions", side_effect=self._all_questions_valid), \
             patch.object(validated.base, "_get_history", return_value=[]), \
             patch.object(validated.base, "_remember"), \
             patch.object(validated, "_annotate_validation") as annotate, \
             patch.object(validated, "_annotate_question_validation"):
            result = validated.generate_assessment_questions(
                topics=topics, language="Spanish", level="A1", count=3, previous_questions=[]
            )

        self.assertEqual(len(result), 3)
        self.assertEqual(planner.call_count, 2)
        summary = annotate.call_args.args[0]
        self.assertTrue(summary["accepted_count_match"])
        self.assertEqual(summary["rejected_objective_count"], 1)
        self.assertEqual(summary["reason_counts"].get("etymology"), 1)

    def test_question_rejected_twice_is_remembered_for_router_topup(self):
        objective = {
            "id": "o1", "key": "bad-sound-meta", "topic_id": "1", "skill": "pronunciation",
            "target": "Identify a sound label", "evidence": "cinco contains two c spellings",
            "question_mode": "contrast",
        }
        topic_sources = {"1": {"title": "Numbers", "type": "vocabulary", "text": "cinco contains two c spellings"}}

        bad_question = {
            "objective_id": "o1", "objective_key": "bad-sound-meta", "topic_id": "1",
            "type": "mcq", "prompt": "Bad phonetic meta question?", "answer": "cinco",
            "distractors": ["cero", "cuatro", "once"],
        }

        def reject_all(questions, objectives_by_id, topic_sources, level):
            return [], [{"reason": "meta_sound_label_trivia", "question": bad_question, "objective_id": "o1"}], {
                "validator_version": "question_validator_v1", "input_count": 1,
                "accepted_count": 0, "rejected_count": 1, "accept_rate": 0.0,
                "reason_counts": {"meta_sound_label_trivia": 1},
            }

        topics = [{"id": 1, "title": "Numbers", "type": "vocabulary", "content": {}}]
        with patch.object(validated, "_topic_evidence_bundle", return_value=(topic_sources["1"]["text"], topic_sources)), \
             patch.object(validated.base, "_plan_objectives", return_value=[objective]), \
             patch.object(validated, "validate_objectives", return_value=([objective], [], {"rejected_count": 0, "reason_counts": {}})), \
             patch.object(validated.base, "_generate_for_objectives", return_value=([bad_question], [])) as writer, \
             patch.object(validated, "validate_questions", side_effect=reject_all), \
             patch.object(validated.base, "_get_history", return_value=[]), \
             patch.object(validated.base, "_remember") as remember, \
             patch.object(validated, "_annotate_validation"), \
             patch.object(validated, "_annotate_question_validation") as q_annotate:
            result = validated.generate_assessment_questions(
                topics=topics, language="Spanish", level="A1", count=1, previous_questions=[]
            )

        self.assertEqual(result, [])
        self.assertEqual(writer.call_count, 2)
        self.assertTrue(any(call.args[1][0].get("objective_key") == "bad-sound-meta" for call in remember.call_args_list if len(call.args) > 1 and call.args[1]))
        summary = q_annotate.call_args.args[0]
        self.assertEqual(summary["accepted_question_count"], 0)
        self.assertEqual(summary["writer_unresolved_count"], 1)
        self.assertEqual(summary["reason_counts"].get("meta_sound_label_trivia"), 2)


if __name__ == "__main__":
    unittest.main()
