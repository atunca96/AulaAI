import json
import re
import unittest
from unittest.mock import patch

from services import assessment_engine_v2


class AssessmentEngineV2Tests(unittest.TestCase):
    def _topic(self, topic_id):
        return {
            "id": topic_id,
            "title": "Test Topic",
            "type": "vocabulary",
            "content": {
                "pages": [
                    {
                        "title": "Core",
                        "items": [
                            {"term": "uno", "translation": "one", "example": "Tengo uno."},
                            {"term": "dos", "translation": "two", "example": "Tengo dos."},
                        ],
                        "rules": [
                            {"rule": "Use forms according to context", "example": "Example"}
                        ],
                    }
                ]
            },
        }

    def _fake_ai(self, messages, **kwargs):
        system = messages[0]["content"]
        if "Assessment Planner V2" in system:
            match = re.search(r"Plan exactly (\d+)", system)
            count = int(match.group(1))
            topic_match = re.search(r"topic_id must be one of: ([^\.]+)", system)
            topic_id = topic_match.group(1).split(",")[0].strip()
            return {
                "objectives": [
                    {
                        "id": f"o{i}",
                        "key": f"objective-{i}",
                        "topic_id": topic_id,
                        "skill": "use",
                        "target": f"distinct target {i}",
                        "evidence": f"evidence {i}",
                        "question_mode": "situational" if i % 2 else "contrast",
                    }
                    for i in range(1, count + 1)
                ]
            }

        self.assertIn("Assessment Writer V2", system)
        user = messages[1]["content"]
        match = re.search(r"OBJECTIVES:\n(.*?)\n\nSOURCE EVIDENCE:", user, flags=re.S)
        objectives = json.loads(match.group(1))
        return {
            "questions": [
                {
                    "objective_id": obj["id"],
                    "prompt": f"Pregunta única {obj['id']} para {obj['target']}?",
                    "translation_en": f"Unique question {obj['id']}?",
                    "translation_tr": f"Benzersiz soru {obj['id']}?",
                    "answer": f"respuesta-{obj['id']}",
                    "distractors": [f"a-{obj['id']}", f"b-{obj['id']}", f"c-{obj['id']}"],
                    "why": "Because it tests the assigned objective.",
                    "why_tr": "Atanan hedefi ölçer.",
                }
                for obj in objectives
            ]
        }

    def test_requested_count_five_is_not_forced_to_ten(self):
        with patch.object(assessment_engine_v2, "_call_ai", side_effect=self._fake_ai):
            result = assessment_engine_v2.generate_assessment_questions(
                topics=[self._topic(1001)],
                language="Spanish",
                level="A1",
                count=5,
                previous_questions=[],
            )
        self.assertEqual(len(result), 5)

    def test_requested_count_thirteen_spans_chunks_and_returns_thirteen(self):
        with patch.object(assessment_engine_v2, "_call_ai", side_effect=self._fake_ai):
            result = assessment_engine_v2.generate_assessment_questions(
                topics=[self._topic(1002)],
                language="Spanish",
                level="A1",
                count=13,
                previous_questions=[],
            )
        self.assertEqual(len(result), 13)
        self.assertEqual(len({q["prompt"] for q in result}), 13)


if __name__ == "__main__":
    unittest.main()
