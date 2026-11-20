import json
import subprocess
import unittest

from trendclip.validate import add_content_quality, inspect_media_quality, probe_video


class ValidateTests(unittest.TestCase):
    def test_content_inspection_accepts_clean_render(self):
        def runner(*args, **kwargs):
            return subprocess.CompletedProcess([], 0, "", "")

        result = inspect_media_quality(__file__, runner=runner)
        self.assertTrue(result["valid"])
        self.assertTrue(all(result["checks"].values()))

    def test_content_inspection_rejects_black_freeze_and_silence(self):
        log = "black_duration:1.2\nfreeze_duration: 2.5\nsilence_duration: 3.4\n"

        def runner(*args, **kwargs):
            return subprocess.CompletedProcess([], 0, "", log)

        result = inspect_media_quality(__file__, runner=runner)
        self.assertFalse(result["valid"])
        self.assertEqual(len(result["errors"]), 3)
        combined = add_content_quality({"valid": True, "errors": []}, result)
        self.assertFalse(combined["valid"])

    def test_static_graphics_policy_still_rejects_black_output(self):
        log = "black_duration:1.2\nfreeze_duration: 2.5\nsilence_duration: 3.4\n"

        def runner(*args, **kwargs):
            return subprocess.CompletedProcess([], 0, "", log)

        result = inspect_media_quality(__file__, runner=runner, allow_static=True, allow_silence=True)
        self.assertFalse(result["valid"])
        self.assertEqual(result["errors"], ["no_black_span_over_0_75_seconds"])

    def test_accepts_expected_probe_payload(self):
        payload = {
            "streams": [
                {"codec_type": "video", "codec_name": "h264", "width": 1080, "height": 1920, "pix_fmt": "yuv420p", "avg_frame_rate": "30/1"},
                {"codec_type": "audio", "codec_name": "aac"},
            ],
            "format": {"duration": "19.0", "format_name": "mov,mp4,m4a,3gp,3g2,mj2", "size": "1234"},
        }

        def runner(*args, **kwargs):
            return subprocess.CompletedProcess([], 0, json.dumps(payload), "")

        self.assertTrue(probe_video(__file__, runner=runner)["valid"])
        self.assertIsNotNone(probe_video(__file__, runner=runner)["sha256"])

    def test_rejects_unexpected_frame_rate(self):
        payload = {
            "streams": [
                {"codec_type": "video", "codec_name": "h264", "width": 1080, "height": 1920, "pix_fmt": "yuv420p", "avg_frame_rate": "60/1"},
                {"codec_type": "audio", "codec_name": "aac"},
            ],
            "format": {"duration": "19.0", "format_name": "mp4", "size": "1234"},
        }

        def runner(*args, **kwargs):
            return subprocess.CompletedProcess([], 0, json.dumps(payload), "")

        self.assertFalse(probe_video(__file__, expected_fps=30, runner=runner)["valid"])

    def test_reports_probe_failure(self):
        def runner(*args, **kwargs):
            raise subprocess.CalledProcessError(1, ["ffprobe"])

        result = probe_video(__file__, runner=runner)
        self.assertFalse(result["valid"])


if __name__ == "__main__":
    unittest.main()

