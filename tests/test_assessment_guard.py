import unittest

from services.assessment_guard import dedupe_questions


class AssessmentGuardTests(unittest.TestCase):
    def test_family_paraphrases_with_same_target_are_deduped(self):
        questions = [
            {"prompt": "¿Quién es el hijo de mi hermano o de mi hermana?", "answer": "Mi sobrino"},
            {"prompt": "Tu hermano acaba de tener un hijo varón. ¿Qué parentesco tiene ese niño contigo?", "answer": "Mi sobrino"},
            {"prompt": "¿Qué parentesco tiene la hermana de tu madre contigo?", "answer": "Es tu tía"},
        ]
        result = dedupe_questions(questions)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["answer"], "Mi sobrino")
        self.assertEqual(result[1]["answer"], "Es tu tía")

    def test_same_answer_in_unrelated_context_is_not_automatically_removed(self):
        questions = [
            {"prompt": "En una boda, ¿cómo presentas formalmente a tu pareja femenina?", "answer": "Es mi esposa"},
            {"prompt": "En un formulario civil, ¿cuál es la relación legal de Ana con Marta tras casarse?", "answer": "Es mi esposa"},
        ]
        result = dedupe_questions(questions)
        self.assertEqual(len(result), 2)

    def test_prior_questions_are_respected(self):
        prior = [
            {"prompt": "La hija de tu hermano es tu...", "answer": "sobrina"},
        ]
        candidates = [
            {"prompt": "Tu hermano tiene una hija. ¿Qué parentesco tiene contigo?", "answer": "sobrina"},
            {"prompt": "El hermano de tu madre es tu...", "answer": "tío"},
        ]
        result = dedupe_questions(candidates, prior=prior)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["answer"], "tío")

    def test_unicode_scripts_are_preserved(self):
        questions = [
            {"prompt": "Кто дочь твоего брата?", "answer": "племянница"},
            {"prompt": "У твоего брата есть дочь. Кто она тебе?", "answer": "племянница"},
        ]
        result = dedupe_questions(questions)
        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()
