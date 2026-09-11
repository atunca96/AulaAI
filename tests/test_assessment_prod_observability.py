import io
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from services import assessment_safety, assessment_telemetry


class AssessmentProdObservabilityTests(unittest.TestCase):
    def test_metric_is_emitted_to_stdout(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            assessment_telemetry._write_metric("ASSESSMENT-METRIC", {"engine": "legacy", "total_ms": 12.3})
        output = buf.getvalue()
        self.assertIn("[ASSESSMENT-METRIC]", output)
        self.assertIn('"engine":"legacy"', output)

    def test_shadow_route_resolves_legacy_primary_on_stdout(self):
        buf = io.StringIO()
        with patch.dict(os.environ, {"ASSESSMENT_ENGINE": "shadow", "ASSESSMENT_SHADOW_PRIMARY": "legacy"}, clear=False):
            with redirect_stdout(buf):
                assessment_safety._log_route("shadow", 10, True)
        output = buf.getvalue()
        self.assertIn("[ASSESSMENT-ROUTE]", output)
        self.assertIn("mode=shadow", output)
        self.assertIn("primary=legacy", output)
        self.assertIn("secondary=v2", output)
        self.assertIn("requested=10", output)


if __name__ == "__main__":
    unittest.main()
