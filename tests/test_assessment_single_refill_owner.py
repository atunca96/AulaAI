import unittest

from services import assessment_legacy_calibration as calibration


class AssessmentSingleRefillOwnerTests(unittest.TestCase):
    def test_repair_count_has_enough_headroom_without_cascade(self):
        self.assertEqual(calibration._repair_count(10, 1), 4)
        self.assertEqual(calibration._repair_count(10, 2), 6)
        self.assertEqual(calibration._repair_count(10, 5), 8)


if __name__ == "__main__":
    unittest.main()
