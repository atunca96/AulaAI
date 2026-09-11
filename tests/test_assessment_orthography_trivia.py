import unittest

from services.assessment_scorecard import _outside_meta_proxy_reason
from services.assessment_objective_validator import validate_objectives
from services.assessment_question_validator import validate_question


class AssessmentOrthographyTriviaTests(unittest.TestCase):
    def test_scorecard_flags_live_tilde_question(self):
        reason = _outside_meta_proxy_reason({
            "prompt": "¿Cuál de estos números se escribe con tilde?",
            "answer": "dieciséis",
            "distractors": ["diecisiete", "dieciocho", "diecinueve"],
        })
        self.assertEqual(reason, "orthography_micro_trivia")

    def test_objective_rejects_accent_micro_trivia_when_topic_is_numbers(self):
        objective = {
            "id": "o1",
            "key": "accented-number",
            "topic_id": "1",
            "skill": "orthographic recognition",
            "target": "Identify which number word carries an orthographic accent mark",
            "evidence": "dieciséis is written with an orthographic accent mark",
            "question_mode": "form-choice",
        }
        sources = {
            "1": {
                "title": "Numbers",
                "type": "vocabulary",
                "text": "dieciséis is written with an orthographic accent mark",
            }
        }
        valid, _, report = validate_objectives([objective], sources, "A1")
        self.assertEqual(valid, [])
        self.assertEqual(report["reason_counts"].get("orthography_micro_trivia"), 1)

    def test_question_rejects_tilde_micro_trivia_when_topic_is_numbers(self):
        objective = {
            "id": "o1",
            "topic_id": "1",
            "skill": "orthographic recognition",
            "target": "Identify the written accent in dieciséis",
            "evidence": "dieciséis is written with a tilde",
            "question_mode": "form-choice",
        }
        question = {
            "prompt": "¿Cuál de estos números se escribe con tilde?",
            "translation_en": "Which of these numbers is written with an accent mark?",
            "answer": "dieciséis",
            "distractors": ["diecisiete", "dieciocho", "diecinueve"],
        }
        source = {
            "title": "Numbers",
            "type": "vocabulary",
            "text": "dieciséis is written with a tilde. diecisiete dieciocho diecinueve",
        }
        ok, reason = validate_question(question, objective, source, "A1")
        self.assertFalse(ok)
        self.assertEqual(reason, "meta_orthography_micro_trivia")

    def test_question_allows_accent_question_when_orthography_is_central(self):
        objective = {
            "id": "o1",
            "topic_id": "1",
            "skill": "orthographic accent",
            "target": "Identify the written accent in canción",
            "evidence": "canción is written with an accent mark",
            "question_mode": "form-choice",
        }
        question = {
            "prompt": "¿Qué palabra lleva tilde?",
            "translation_en": "Which word has a written accent mark?",
            "answer": "canción",
            "distractors": ["casa", "mesa", "libro"],
        }
        source = {
            "title": "Spanish Orthography and Accentuation",
            "type": "orthography",
            "text": "canción is written with an accent mark. casa mesa libro",
        }
        ok, reason = validate_question(question, objective, source, "B1")
        self.assertTrue(ok)
        self.assertIsNone(reason)


if __name__ == "__main__":
    unittest.main()
