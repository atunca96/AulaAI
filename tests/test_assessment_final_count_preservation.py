import types
import unittest
from collections import Counter

from services import assessment_legacy_calibration as calibration
from services import assessment_legacy_filter as gate


class AssessmentFinalCountPreservationTests(unittest.TestCase):
    def test_final_gate_is_structural_only_after_candidate_quality_pass(self):
        original_filter = gate._filter_batch
        original_refills = gate._MAX_REFILL_ROUNDS
        original_flag = getattr(gate, "_legacy_finalizer_structural_only", False)
        original_install_flag = getattr(types.SimpleNamespace(), "_legacy_candidate_calibration_installed", False)

        fake_ai = types.SimpleNamespace(ai_generate_questions=lambda *args, **kwargs: [])
        try:
            calibration.install(fake_ai)
            question = {
                "prompt": "¿Cuál forma lleva tilde según la regla enseñada?",
                "answer": "veintitrés",
                "distractors": ["veintidos", "veinticuatro", "veintiseis"],
            }
            clean, rejected, reasons = gate._filter_batch(
                [question],
                source_text="TOPIC Numbers (vocabulary)",
                accepted=[],
                prior=[],
                operation_counts=Counter(),
                requested=10,
            )
            self.assertEqual(clean, [question])
            self.assertEqual(rejected, [])
            self.assertEqual(dict(reasons), {})
            self.assertEqual(gate._MAX_REFILL_ROUNDS, 0)
        finally:
            gate._filter_batch = original_filter
            gate._MAX_REFILL_ROUNDS = original_refills
            if not original_flag and hasattr(gate, "_legacy_finalizer_structural_only"):
                delattr(gate, "_legacy_finalizer_structural_only")

    def test_structurally_invalid_item_is_still_rejected(self):
        fake_ai = types.SimpleNamespace(ai_generate_questions=lambda *args, **kwargs: [])
        calibration.install(fake_ai)
        broken = {"prompt": "Pregunta", "answer": "uno", "distractors": ["dos", "tres"]}
        clean, rejected, reasons = gate._filter_batch(
            [broken],
            source_text="TOPIC Numbers (vocabulary)",
            accepted=[],
            prior=[],
            operation_counts=Counter(),
            requested=10,
        )
        self.assertEqual(clean, [])
        self.assertEqual(rejected, [broken])
        self.assertEqual(reasons["invalid_mcq_structure"], 1)


if __name__ == "__main__":
    unittest.main()
