import unittest

from services.assessment_guard import dedupe_questions


class AssessmentGuardTests(unittest.TestCase):
    def test_family_paraphrases_with_same_target_are_deduped(self):
        questions = [
            {"prompt": "¿Quién es el hijo de mi hermano o de mi hermana?", "answer": "Mi sobrino"},
            {"prompt": "Tu hermano acaba de tener un hijo varón. ¿Qué parentesco tiene ese niño contigo?", "answer": "Es tu sobrino"},
            {"prompt": "¿Qué parentesco tiene la hermana de tu madre contigo?", "answer": "Es tu tía"},
        ]
        result = dedupe_questions(questions)
        self.assertEqual(len(result), 2)

    def test_same_answer_in_unrelated_context_is_not_automatically_removed(self):
        questions = [
            {"prompt": "En una boda, ¿cómo presentas formalmente a tu pareja femenina?", "answer": "Es mi esposa"},
            {"prompt": "En un ejercicio de posesivos, ¿qué palabra completa 'Esta casa es ___'?", "answer": "Es mi esposa"},
        ]
        result = dedupe_questions(questions)
        self.assertEqual(len(result), 2)

    def test_prior_questions_are_respected(self):
        prior = [{"prompt": "La hija de tu hermano es tu...", "answer": "sobrina"}]
        candidates = [
            {"prompt": "Tu hermano tiene una hija. ¿Qué parentesco tiene contigo?", "answer": "Es tu sobrina"},
            {"prompt": "El hermano de tu madre es tu...", "answer": "tío"},
        ]
        result = dedupe_questions(candidates, prior=prior)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["answer"], "tío")

    def test_cyrillic_paraphrases_are_deduped(self):
        questions = [
            {"prompt": "Кто дочь твоего брата?", "answer": "племянница"},
            {"prompt": "У твоего брата есть дочь. Кто она тебе?", "answer": "племянница"},
        ]
        result = dedupe_questions(questions)
        self.assertEqual(len(result), 1)

    def test_japanese_no_space_script_is_supported(self):
        questions = [
            {"prompt": "兄の娘はあなたにとって誰ですか", "answer": "姪"},
            {"prompt": "あなたの兄に娘がいます。その子はあなたの何ですか", "answer": "姪"},
        ]
        result = dedupe_questions(questions)
        self.assertEqual(len(result), 1)

    def test_chinese_different_concepts_survive(self):
        questions = [
            {"prompt": "你哥哥的女儿和你是什么关系", "answer": "侄女"},
            {"prompt": "你妈妈的哥哥和你是什么关系", "answer": "舅舅"},
        ]
        result = dedupe_questions(questions)
        self.assertEqual(len(result), 2)

    def test_canonical_objective_key_dedupes_different_surface_questions(self):
        questions = [
            {
                "prompt": "¿Qué conector aparece en cuarenta y cinco?",
                "answer": "y",
                "why": "[[OBJ:numbers:30-plus-conjunction:apply]] La conjunción y une decena y unidad.",
            },
            {
                "prompt": "¿Cómo se enlazan treinta y dos?",
                "answer": "con y",
                "why": "[[OBJ:numbers:30-plus-conjunction:apply]] La misma regla se aplica aquí.",
            },
        ]
        result = dedupe_questions(questions)
        self.assertEqual(len(result), 1)
        self.assertNotIn("[[OBJ:", result[0]["why"])

    def test_distinct_objective_keys_survive(self):
        questions = [
            {
                "prompt": "¿Qué forma adopta uno delante de un sustantivo masculino?",
                "answer": "un",
                "why": "[[OBJ:numbers:uno-apocope:apply]] Uno se apocopa delante de masculino singular.",
            },
            {
                "prompt": "¿Qué conector aparece en cuarenta y cinco?",
                "answer": "y",
                "why": "[[OBJ:numbers:30-plus-conjunction:apply]] Y une decena y unidad.",
            },
        ]
        result = dedupe_questions(questions)
        self.assertEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main()
