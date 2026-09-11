import unittest

from services.assessment_pseudoform_precision import _hard_reject_cluster


class AssessmentPseudoformPrecisionTests(unittest.TestCase):
    def test_two_suspicious_near_forms_are_not_hard_rejected(self):
        self.assertFalse(_hard_reject_cluster(2))

    def test_three_suspicious_near_forms_are_hard_rejected(self):
        self.assertTrue(_hard_reject_cluster(3))


if __name__ == "__main__":
    unittest.main()
