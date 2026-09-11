import unittest

from services import assessment_legacy_calibration as calibration
from services import assessment_legacy_filter as gate


class AssessmentPseudoformCalibrationTests(unittest.TestCase):
    def test_single_near_form_is_not_strong_cluster(self):
        question = {
            "prompt": "Choose the form that fits the context.",
            "answer": "accepten",
            "distractors": ["aceptan", "rechazan", "permiten"],
        }
        source = "TOPIC Opinions (vocabulary)\nacepten aceptan rechazan permiten"
        self.assertLess(calibration._pseudoform_suspicious_count(gate, question, source), 2)

    def test_multiple_unsupported_spelling_neighbours_are_strong_cluster(self):
        question = {
            "prompt": "Choose the correct form.",
            "answer": "dos",
            "distractors": ["doz", "dós", "cuatro"],
        }
        source = "TOPIC Numbers (vocabulary)\ndos cuatro"
        self.assertGreaterEqual(calibration._pseudoform_suspicious_count(gate, question, source), 2)


if __name__ == "__main__":
    unittest.main()
