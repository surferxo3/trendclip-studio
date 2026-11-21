import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

import numpy as np

from trendclip.media_pipeline import MediaPipelineError, _download_analysis_audio, _download_analysis_proxy, _download_render_section, _run, _vertical_frame, _yt_dlp, ingest_source, score_moments


class MediaPipelineTests(unittest.TestCase):
    @patch("trendclip.media_pipeline._extract_audio")
    @patch("trendclip.media_pipeline._download_analysis_proxy", return_value=None)
    @patch("trendclip.media_pipeline._download_analysis_audio")
    @patch("trendclip.media_pipeline._run")
    def test_ingestion_downloads_audio_first_and_defers_video(self, run, download_audio, _download_proxy, extract_audio):
        run.return_value = CompletedProcess(
            ["yt-dlp"],
            0,
            '{"duration": 120, "title": "Demo", "channel": "Creator", "webpage_url": "https://www.youtube.com/watch?v=demo"}',
            "",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_audio = root / "download.m4a"
            raw_audio.write_bytes(b"audio")
            download_audio.return_value = raw_audio

            def prepare_audio(_source, destination):
                destination.write_bytes(b"wav")

            extract_audio.side_effect = prepare_audio
            info = ingest_source(
                root,
                "https://www.youtube.com/watch?v=demo",
                rights={"category": "third-party-review-draft", "allowed_platforms": ["youtube"], "commercial_use_scope": "unknown", "attribution_required": False},
            )
            job = root / "state" / "jobs" / info["job_id"]
            self.assertTrue((job / "audio.wav").is_file())
            self.assertFalse((job / "source.mp4").exists())
        self.assertEqual(info["analysis_mode"], "audio-first-fallback")
        self.assertEqual(info["video_download"], "deferred-until-draft-selection")
        self.assertFalse(download_audio.call_args.kwargs["section_limited"])
        self.assertFalse(_download_proxy.call_args.kwargs["section_limited"])

    @patch("trendclip.media_pipeline._run")
    def test_full_source_download_avoids_realtime_section_cut(self, run):
        with tempfile.TemporaryDirectory() as directory:
            job = Path(directory)

            def execute(command, **_kwargs):
                (job / "analysis-audio.webm").write_bytes(b"audio")
                return CompletedProcess(command, 0, "", "")

            run.side_effect = execute
            result = _download_analysis_audio(
                ["yt-dlp"],
                "https://www.youtube.com/watch?v=demo",
                job,
                120,
                section_limited=False,
            )
        self.assertIsNotNone(result)
        self.assertNotIn("--download-sections", run.call_args.args[0])

    @patch("trendclip.media_pipeline._run")
    def test_visual_proxy_uses_low_resolution_video_only(self, run):
        with tempfile.TemporaryDirectory() as directory:
            job = Path(directory)

            def execute(command, **_kwargs):
                (job / "analysis-proxy.mp4").write_bytes(b"proxy")
                return CompletedProcess(command, 0, "", "")

            run.side_effect = execute
            result = _download_analysis_proxy(["yt-dlp"], "https://www.youtube.com/watch?v=demo", job, 90)
        self.assertIsNotNone(result)
        command = run.call_args.args[0]
        self.assertIn("bv*[height<=240]/wv*", command)
        self.assertIn("*0-90.000", command)

    @patch("trendclip.media_pipeline._yt_dlp", return_value=["yt-dlp"])
    @patch("trendclip.media_pipeline._run")
    def test_render_downloads_only_selected_section(self, run, _ytdlp):
        commands = []

        def execute(command, **_kwargs):
            commands.append(command)
            destination = Path(command[command.index("-o") + 1])
            destination.write_bytes(b"video")
            return CompletedProcess(command, 0, "", "")

        run.side_effect = execute
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "section.mp4"
            offset = _download_render_section(
                {"duration": 300, "source_url": "https://www.youtube.com/watch?v=demo", "authentication": "anonymous"},
                {"start": 42, "end": 64},
                destination,
            )
        self.assertEqual(offset, 40)
        self.assertIn("--download-sections", commands[0])
        self.assertIn("*40.000-66.000", commands[0])
        self.assertIn("--force-keyframes-at-cuts", commands[0])

    def test_ingestion_requires_source_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(MediaPipelineError, "provenance"):
                ingest_source(
                    Path(directory),
                    "https://www.youtube.com/watch?v=example",
                    rights_confirmed=False,
                )

    def test_moment_scoring_prefers_energy_and_hype(self):
        db = np.full(80, -35.0)
        db[38:42] = -4.0
        words = [
            {"w": "ordinary", "s": 5.0, "e": 5.5},
            {"w": "no way", "s": 40.0, "e": 40.6},
            {"w": "look at this", "s": 41.0, "e": 42.0},
        ]
        candidates = score_moments(words, db, [], 80.0, top=2)
        self.assertTrue(candidates)
        self.assertLessEqual(candidates[0]["start"], 40)
        self.assertGreaterEqual(candidates[0]["end"], 41)
        self.assertIn("hype language", candidates[0]["why"])

    def test_draft_layouts_are_visibly_different(self):
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        frame[:, :640] = (20, 80, 220)
        frame[:, 640:] = (220, 140, 20)
        balanced = _vertical_frame(frame, layout="balanced")
        punch = _vertical_frame(frame, layout="punch")
        clean = _vertical_frame(frame, layout="clean")
        self.assertEqual(balanced.shape, (1920, 1080, 3))
        self.assertEqual(punch.shape, balanced.shape)
        self.assertEqual(clean.shape, balanced.shape)
        self.assertGreater(float(np.mean(np.abs(balanced.astype(float) - punch.astype(float)))), 5.0)
        self.assertGreater(float(np.mean(np.abs(balanced.astype(float) - clean.astype(float)))), 1.0)

    @patch("trendclip.media_pipeline.shutil.which", return_value="/opt/node")
    def test_authenticated_downloader_uses_chrome_and_node_challenge_solver(self, _which):
        command = _yt_dlp(use_browser_cookies=True)
        self.assertIn("node:/opt/node", command)
        self.assertEqual(command[-2:], ["--cookies-from-browser", "chrome"])

    @patch("trendclip.media_pipeline.subprocess.run")
    def test_anonymous_sign_in_failure_points_to_setting_without_traceback(self, run):
        run.return_value = CompletedProcess(
            ["yt-dlp"], 1, "", "ERROR: Sign in to confirm you're not a bot"
        )
        with self.assertRaisesRegex(MediaPipelineError, "Enable the Chrome YouTube session"):
            _run(["yt-dlp", "https://www.youtube.com/watch?v=demo"])

    @patch("trendclip.media_pipeline.subprocess.run")
    def test_authenticated_sign_in_failure_points_to_chrome(self, run):
        run.return_value = CompletedProcess(
            ["yt-dlp"], 1, "", "ERROR: Sign in to confirm you're not a bot"
        )
        with self.assertRaisesRegex(MediaPipelineError, "current Chrome session"):
            _run(["yt-dlp", "--cookies-from-browser", "chrome", "https://www.youtube.com/watch?v=demo"])

    @patch("trendclip.media_pipeline.subprocess.run")
    def test_expired_media_link_has_actionable_retry_message(self, run):
        run.return_value = CompletedProcess(
            ["yt-dlp"], 1, "", "[https] HTTP error 403 Forbidden: Server returned 403 Forbidden"
        )
        with self.assertRaisesRegex(MediaPipelineError, "temporary media link"):
            _run(["yt-dlp", "https://www.youtube.com/watch?v=demo"])


if __name__ == "__main__":
    unittest.main()
