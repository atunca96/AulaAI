import unittest

from services.assessment_question_validator import validate_question


class AssessmentQuestionValidatorTests(unittest.TestCase):
    def _source(self, title="Numbers", topic_type="vocabulary", text=""):
        return {"title": title, "type": topic_type, "text": text}

    def test_rejects_live_soft_c_outside_word(self):
        objective = {
            "id": "o1", "topic_id": "1", "skill": "pronunciation",
            "target": "Recognize the soft c sound in cero", "evidence": "cero starts with a soft c sound",
            "question_mode": "form-choice",
        }
        question = {
            "prompt": "¿Qué palabra empieza con el mismo sonido suave de la 'c' que «cero»?",
            "answer": "cine", "distractors": ["casa", "cosa", "curso"],
        }
        ok, reason = validate_question(
            question, objective, self._source(text="cero starts with a soft c sound"), "A1"
        )
        self.assertFalse(ok)
        self.assertTrue(reason.startswith("meta_") or reason == "answer_unsupported")

    def test_rejects_live_cinco_phonetic_meta_question(self):
        objective = {
            "id": "o1", "topic_id": "1", "skill": "pronunciation",
            "target": "Distinguish the two c sounds in cinco", "evidence": "cinco contains two c spellings",
            "question_mode": "contrast",
        }
        question = {
            "prompt": "En la palabra «cinco», ¿cómo se pronuncian las dos letras «c»?",
            "answer": "La primera es suave (/s/ o /θ/) y la segunda es fuerte (/k/).",
            "distractors": ["Ambas suaves", "Ambas fuertes", "Primera fuerte y segunda suave"],
        }
        ok, reason = validate_question(
            question, objective, self._source(text="cinco contains two c spellings"), "A1"
        )
        self.assertFalse(ok)
        self.assertTrue(reason.startswith("meta_"))

    def test_rejects_unsupported_answer_word(self):
        objective = {
            "id": "o1", "topic_id": "1", "skill": "lexical meaning",
            "target": "Recognize cero", "evidence": "cero means zero", "question_mode": "meaning",
        }
        question = {
            "prompt": "¿Qué palabra significa cero?", "answer": "cine",
            "distractors": ["cero", "uno", "dos"],
        }
        ok, reason = validate_question(
            question, objective, self._source(text="cero means zero. uno means one. dos means two."), "A1"
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "answer_unsupported")

    def test_rejects_fake_near_form_distractors_for_contextual_vocabulary(self):
        objective = {
            "id": "o1", "topic_id": "1", "skill": "contextual use",
            "target": "Use dos when referring to two people", "evidence": "dos means two",
            "question_mode": "situational",
        }
        question = {
            "prompt": "Tengo _____ hermanas.", "answer": "dos",
            "distractors": ["do", "dosa", "dosas"],
        }
        ok, reason = validate_question(
            question, objective, self._source(text="dos means two. Tengo dos hermanas."), "A1"
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "pseudoform_distractors")

    def test_rejects_parenthetical_numeric_cue_even_when_objective_has_no_digit(self):
        objective = {
            "id": "o1", "topic_id": "1", "skill": "contextual use",
            "target": "Use seis for a train ticket price",
            "evidence": "seis is used for the ticket price in the lesson",
            "question_mode": "completion",
        }
        question = {
            "prompt": "—¿Cuánto cuesta? —Cuesta _____ euros (6 €).",
            "translation_en": "How much is it? It costs _____ euros (6 €).",
            "answer": "seis", "distractors": ["cinco", "siete", "ocho"],
        }
        ok, reason = validate_question(
            question, objective,
            self._source(text="The ticket costs seis euros in the lesson. seis cinco siete ocho."),
            "A1",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "answer_revealed_by_numeric_cue")

    def test_allows_cross_language_question_via_english_translation_bridge(self):
        objective = {
            "id": "o1", "topic_id": "1", "skill": "contextual use",
            "target": "Use cero to express zero temperature",
            "evidence": "cero is used for zero degrees",
            "question_mode": "completion",
        }
        question = {
            "prompt": "El termómetro marca _____ grados esta noche.",
            "translation_en": "The thermometer reads _____ degrees tonight.",
            "translation_tr": "Termometre bu gece _____ dereceyi gösteriyor.",
            "answer": "cero", "distractors": ["uno", "dos", "tres"],
        }
        ok, reason = validate_question(
            question, objective,
            self._source(text="cero is used for zero degrees. uno dos tres"), "A1"
        )
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_allows_grounded_context_question(self):
        objective = {
            "id": "o1", "topic_id": "1", "skill": "contextual use",
            "target": "Use cero for zero degrees", "evidence": "El termómetro marca cero grados",
            "question_mode": "completion",
        }
        question = {
            "prompt": "El termómetro marca _____ grados esta noche.",
            "translation_en": "The thermometer reads _____ degrees tonight.",
            "answer": "cero", "distractors": ["uno", "dos", "tres"],
        }
        ok, reason = validate_question(
            question, objective,
            self._source(text="El termómetro marca cero grados. uno dos tres"), "A1"
        )
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_allows_derived_spelling_form_from_taught_rule(self):
        objective = {
            "id": "o1", "topic_id": "1", "skill": "orthographic form",
            "target": "Apply the fused spelling rule for 16 to 29", "evidence": "16 to 29 are written as one fused word",
            "question_mode": "form-choice",
        }
        question = {
            "prompt": "¿Cómo se escribe 24?", "translation_en": "How do you write 24?",
            "answer": "veinticuatro",
            "distractors": ["veinte y cuatro", "veinti cuatro", "veintecuatro"],
        }
        ok, reason = validate_question(
            question, objective,
            self._source(text="Los números 16 a 29 se escriben como una palabra fusionada."), "A1"
        )
        self.assertTrue(ok)
        self.assertIsNone(reason)


if __name__ == "__main__":
    unittest.main()
