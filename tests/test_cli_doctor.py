import io
import unittest
from unittest.mock import patch

from trendclip.cli import _system_fix, run_doctor


class DoctorTests(unittest.TestCase):
    @patch("trendclip.cli.platform.system", return_value="Windows")
    def test_windows_ffmpeg_fix_is_actionable(self, _system):
        self.assertIn("winget install", _system_fix("FFmpeg"))

    @patch("trendclip.cli.platform.system", return_value="Darwin")
    def test_macos_node_fix_is_actionable(self, _system):
        self.assertIn("brew install node", _system_fix("Node.js"))

    @patch("trendclip.cli.doctor_checks")
    def test_optional_codex_does_not_fail_doctor(self, checks):
        checks.return_value = [
            ("Python 3.10+", True, "3.12", True),
            ("Codex assistance", False, "optional; not installed", False),
        ]
        output = io.StringIO()
        with patch("sys.stdout", output):
            result = run_doctor()
        self.assertEqual(result, 0)
        self.assertIn("INFO  Codex assistance", output.getvalue())

    @patch("trendclip.cli.doctor_checks")
    def test_required_failure_returns_nonzero_with_fix(self, checks):
        checks.return_value = [("FFmpeg", False, "not found", True)]
        output = io.StringIO()
        with patch("sys.stdout", output):
            result = run_doctor()
        self.assertEqual(result, 1)
        self.assertIn("Fix:", output.getvalue())


if __name__ == "__main__":
    unittest.main()
