import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from trendclip.dashboard import ACTIVE_JOB_IDS, _claim_job, _release_job, _save_discovery_safely, _terminate_worker, _worker_process_options, codex_smoke_test, project_status, serve_dashboard
from trendclip.media_pipeline import MediaPipelineError


class DashboardTests(unittest.TestCase):
    def test_duplicate_media_job_is_rejected_until_release(self):
        job_id = "abc123abc123"
        try:
            _claim_job(job_id)
            with self.assertRaisesRegex(MediaPipelineError, "already processing"):
                _claim_job(job_id)
        finally:
            _release_job(job_id)
        self.assertNotIn(job_id, ACTIVE_JOB_IDS)

    def test_worker_process_options_are_cross_platform(self):
        self.assertEqual(_worker_process_options("posix"), {"start_new_session": True})
        windows = _worker_process_options("nt")
        self.assertIn("creationflags", windows)
        self.assertNotIn("start_new_session", windows)

    @patch("trendclip.dashboard.subprocess.run")
    def test_windows_worker_termination_uses_taskkill_tree(self, run):
        process = Mock()
        process.pid = 321
        process.poll.return_value = None
        run.return_value.returncode = 0
        _terminate_worker(process, "nt")
        self.assertEqual(run.call_args.args[0], ["taskkill", "/PID", "321", "/T", "/F"])

    @patch("trendclip.dashboard.invoke_codex")
    def test_codex_smoke_uses_bounded_synthetic_candidates(self, invoke_mock):
        invoke_mock.return_value = {"ranked_candidate_ids": ["2", "1", "3"], "rationale": "complete payoff"}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config").mkdir()
            (root / "config" / "settings.json").write_text(json.dumps({"codex": {"enabled": True}}), encoding="utf-8")
            result = codex_smoke_test(root)
        self.assertEqual(result["ranked_candidate_ids"][0], "2")
        payload = invoke_mock.call_args.args[2]
        self.assertEqual(len(payload["candidates"]), 3)
        self.assertNotIn("url", payload["candidates"][0])

    def test_empty_refresh_preserves_last_useful_discovery_report(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "latest.json"
            path.write_text(json.dumps({"candidates": [{"url": "https://www.youtube.com/watch?v=kept"}], "source_errors": []}), encoding="utf-8")
            result = _save_discovery_safely({"candidates": [], "source_errors": [{"source": "YouTube", "error": "temporary"}]}, path)
            persisted = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(result["candidates"][0]["url"], "https://www.youtube.com/watch?v=kept")
        self.assertIn("refresh_warning", persisted)

    def test_status_reports_topics_and_latest_validated_export(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config" / "topics").mkdir(parents=True)
            (root / "config" / "topics" / "demo.json").write_text("{}", encoding="utf-8")
            output = root / "output" / "demo" / "2026-11-19"
            output.mkdir(parents=True)
            (output / "clip-001.mp4").write_bytes(b"video")
            (output / "clip-001.json").write_text(
                json.dumps({"suggested_title": "Demo"}), encoding="utf-8"
            )
            (output / "validation.json").write_text(
                json.dumps({"valid": True, "observed": {"duration_seconds": 20}}),
                encoding="utf-8",
            )
            (output / "clip-best-story.mp4").write_bytes(b"variation")
            (output / "clip-best-story.json").write_text(json.dumps({"draft": {"layout": "balanced"}}), encoding="utf-8")
            (output / "validation-best-story.json").write_text(json.dumps({"valid": True}), encoding="utf-8")
            status = project_status(root)
        self.assertEqual(status["topics"], ["demo"])
        self.assertTrue(status["latest_export"]["validation"]["valid"])
        self.assertEqual(status["latest_export"]["variations"][0]["layout"], "balanced")
        self.assertEqual(status["publishing"]["mode"], "manual-only")

    @patch("trendclip.dashboard.webbrowser.open", return_value=True)
    @patch("trendclip.dashboard.ThreadingHTTPServer")
    def test_studio_opens_browser_after_server_is_created(self, server_class, browser_open):
        server_class.return_value.serve_forever.side_effect = KeyboardInterrupt
        with tempfile.TemporaryDirectory() as directory:
            serve_dashboard(Path(directory), port=8765, refresh=False, open_browser=True)
        server_class.assert_called_once()
        browser_open.assert_called_once_with("http://127.0.0.1:8765")
        server_class.return_value.server_close.assert_called_once()


if __name__ == "__main__":
    unittest.main()

