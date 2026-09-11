import unittest

from services import assessment_legacy_calibration as calibration
from services.assessment_small_supplement_pool import install


class SmallSupplementPoolTests(unittest.TestCase):
    def test_small_requests_get_headroom(self):
        install()
        self.assertEqual(calibration._candidate_count(None, (), {}, 1), 6)
        self.assertEqual(calibration._candidate_count(None, (), {}, 2), 6)
        self.assertEqual(calibration._candidate_count(None, (), {}, 3), 8)
        self.assertEqual(calibration._candidate_count(None, (), {}, 4), 10)

    def test_normal_requests_delegate_to_existing_policy(self):
        install()

        class Guard:
            @staticmethod
            def _norm(value):
                return str(value or "").lower()

            @staticmethod
            def _arg(args, kwargs, name, index, default=None):
                return kwargs.get(name, default)

        # A1 vocabulary keeps the existing 20% headroom policy: 10 -> 12.
        self.assertEqual(
            calibration._candidate_count(
                Guard(), (), {"topic_type": "vocabulary", "level": "A1"}, 10
            ),
            12,
        )


if __name__ == "__main__":
    unittest.main()
