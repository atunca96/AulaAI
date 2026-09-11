import unittest

from services.assessment_objective_validator import validate_objectives


class AssessmentObjectiveValidatorTests(unittest.TestCase):
    def _sources(self, title="Numbers", topic_type="grammar", text=None):
        return {
            "1": {
                "title": title,
                "type": topic_type,
                "text": text or "uno changes to un before a masculine singular noun such as café. dos is invariant.",
            }
        }

    def test_accepts_grounded_form_function_objective(self):
        obj = {
            "id": "o1", "key": "uno-before-masculine", "topic_id": "1",
            "skill": "grammar use", "target": "Use un before a masculine singular noun",
            "evidence": "uno changes to un before a masculine singular noun",
            "question_mode": "form-choice",
        }
        valid, rejected, report = validate_objectives([obj], self._sources(), "A1")
        self.assertEqual(len(valid), 1)
        self.assertEqual(rejected, [])
        self.assertEqual(report["accepted_count"], 1)

    def test_rejects_unsupported_evidence(self):
        obj = {
            "id": "o1", "key": "invented", "topic_id": "1",
            "skill": "grammar use", "target": "Use an invented suffix",
            "evidence": "the lesson teaches a completely invented suffix xyz",
            "question_mode": "form-choice",
        }
        valid, _, report = validate_objectives([obj], self._sources(), "A1")
        self.assertEqual(valid, [])
        self.assertEqual(report["reason_counts"].get("evidence_unsupported"), 1)

    def test_rejects_a1_etymology_even_when_source_mentions_it(self):
        source = self._sources(text="The word cinco has an etymological history derived from Latin quinque.")
        obj = {
            "id": "o1", "key": "cinco-etymology", "topic_id": "1",
            "skill": "historical knowledge", "target": "Identify the etymological origin of cinco",
            "evidence": "cinco has an etymological history derived from Latin quinque",
            "question_mode": "meaning",
        }
        valid, _, report = validate_objectives([obj], source, "A1")
        self.assertEqual(valid, [])
        self.assertEqual(report["reason_counts"].get("etymology"), 1)

    def test_rejects_a1_abstract_diphthong_terminology(self):
        source = self._sources(text="seis contains the diphthong ei in its written form.")
        obj = {
            "id": "o1", "key": "seis-diphthong", "topic_id": "1",
            "skill": "phonology terminology", "target": "Identify the diphthong ei in seis",
            "evidence": "seis contains the diphthong ei in its written form",
            "question_mode": "form-choice",
        }
        valid, _, report = validate_objectives([obj], source, "A1")
        self.assertEqual(valid, [])
        self.assertEqual(report["reason_counts"].get("abstract_phonology_terminology"), 1)

    def test_rejects_same_lexical_lookup_disguised_with_another_number(self):
        first = {
            "id": "o1", "key": "number-seven", "topic_id": "1",
            "skill": "lexical meaning", "target": "Recognize the Spanish number word for 7",
            "evidence": "siete means seven", "question_mode": "meaning",
        }
        second = {
            "id": "o2", "key": "number-eight", "topic_id": "1",
            "skill": "lexical meaning", "target": "Recognize the Spanish number word for 8",
            "evidence": "ocho means eight", "question_mode": "meaning",
        }
        source = self._sources(text="siete means seven. ocho means eight.")
        valid, _, report = validate_objectives([second], source, "A1", accepted=[first])
        self.assertEqual(valid, [])
        self.assertEqual(report["reason_counts"].get("duplicate_same_lookup_operation"), 1)

    def test_allows_practical_higher_level_pronunciation_when_topic_is_central(self):
        source = self._sources(
            title="Pronunciation and diphthongs", topic_type="pronunciation",
            text="Learners practise pronouncing the diphthong ei clearly in connected speech.",
        )
        obj = {
            "id": "o1", "key": "pronounce-ei", "topic_id": "1",
            "skill": "pronunciation use", "target": "Pronounce the diphthong ei clearly in connected speech",
            "evidence": "practise pronouncing the diphthong ei clearly in connected speech",
            "question_mode": "situational",
        }
        valid, _, _ = validate_objectives([obj], source, "B2")
        self.assertEqual(len(valid), 1)


if __name__ == "__main__":
    unittest.main()
