import unittest

from services.assessment_scorecard import _outside_meta_proxy_reason, build_scorecard


class AssessmentScorecardCalibrationTests(unittest.TestCase):
    def test_live_etymology_failure_is_flagged(self):
        q = {
            "prompt": "¿Cuál es la característica etimológica y estructural de los números del 0 al 15 en español?",
            "answer": "Tienen raíces únicas e irregulares derivadas del latín.",
            "distractors": ["a", "b", "c"],
        }
        self.assertEqual(_outside_meta_proxy_reason(q), "etymology")

    def test_live_diphthong_failure_is_flagged(self):
        q = {
            "prompt": "¿Qué número del 0 al 15 presenta el diptongo decreciente 'ei' en su escritura?",
            "answer": "seis",
            "distractors": ["tres", "diez", "once"],
        }
        self.assertEqual(_outside_meta_proxy_reason(q), "phonology_terminology")

    def test_live_sound_label_failure_is_flagged(self):
        q = {
            "prompt": "¿Cuál palabra contiene dos sonidos de 'c' diferentes, uno suave y uno fuerte?",
            "answer": "cinco",
            "distractors": ["cero", "ocho", "doce"],
        }
        self.assertEqual(_outside_meta_proxy_reason(q), "sound_label_trivia")

    def test_live_ipa_transcription_failure_is_flagged(self):
        q = {
            "prompt": "¿Qué número básico contiene dos sonidos diferentes de la letra 'c' (/s/ o /θ/ y luego /k/)?",
            "answer": "cinco",
            "distractors": ["ocho", "tres", "siete"],
        }
        self.assertEqual(_outside_meta_proxy_reason(q), "phonetic_transcription_trivia")

    def test_live_tap_label_failure_is_flagged(self):
        q = {
            "prompt": "¿Cuál de los siguientes números contiene un sonido de 'r' simple (tap)?",
            "answer": "tres",
            "distractors": ["ocho", "diez", "seis"],
        }
        self.assertEqual(_outside_meta_proxy_reason(q), "sound_label_trivia")

    def test_normal_form_function_question_is_not_flagged(self):
        q = {
            "prompt": "¿Cómo cambia el número 'uno' cuando precede a un sustantivo masculino como 'café'?",
            "answer": "un",
            "distractors": ["una", "unos", "unas"],
        }
        self.assertIsNone(_outside_meta_proxy_reason(q))

    def test_numeric_range_is_not_mistaken_for_arithmetic(self):
        q = {
            "prompt": "¿Qué regla se aplica a los números 16-29 en español?",
            "answer": "Se escriben fusionados.",
            "distractors": ["Con guion", "Con y", "Separados"],
        }
        self.assertIsNone(_outside_meta_proxy_reason(q))

    def test_composite_is_explicitly_not_cutover_eligible(self):
        q = {
            "prompt": "¿Cuál es la característica etimológica de esta palabra?",
            "answer": "latina",
            "distractors": ["griega", "árabe", "germánica"],
        }
        score = build_scorecard([q], 1, "")
        self.assertFalse(score["cutover_eligible"])
        self.assertTrue(score["composite_score_provisional"])
        self.assertEqual(score["outside_meta_proxy_rate"], 1.0)
        self.assertEqual(score["outside_meta_proxy_reason_counts"]["etymology"], 1)


if __name__ == "__main__":
    unittest.main()
