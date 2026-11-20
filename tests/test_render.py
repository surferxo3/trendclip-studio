import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from trendclip.cli import main, promote_export
from trendclip.config import load_topic
from trendclip.render import RenderError, build_filter_graph, write_metadata
from trendclip.raster import FONT


ROOT = Path(__file__).resolve().parent.parent


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.config = load_topic(ROOT / "config" / "topics" / "gta6.json")

    def test_filter_graph_is_topic_independent_and_has_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            graph, duration = build_filter_graph(self.config)
        self.assertIn("xfade=", graph)
        self.assertIn("sine=f=110", graph)
        self.assertGreaterEqual(duration, 15)
        self.assertLessEqual(duration, 30)

    def test_all_scene_characters_are_supported(self):
        text = "".join(
            scene.eyebrow + scene.headline + scene.body for scene in self.config.scenes
        ).upper()
        self.assertEqual(sorted(set(text) - set(FONT) - {"\n"}), [])

    def test_metadata_records_content_disclosure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "clip.json"
            write_metadata(
                self.config,
                path,
                Path("clip.mp4"),
                {"generated_at": "2026-11-19T00:00:00+00:00", "sha256": "abc"},
                {"valid": True},
            )
            payload = json.loads(path.read_text())
        self.assertEqual(payload["project_name"], "TrendClip Studio")
        self.assertEqual(payload["validation_status"], "passed")
        self.assertIn("not gameplay", payload["content_disclosure"].lower())

    def test_non_gaming_disclosure_is_config_driven(self):
        raw = json.loads((ROOT / "config" / "topics" / "gta6.json").read_text())
        raw["slug"] = "ai-news"
        raw["topic_name"] = "AI News"
        raw["metadata"]["content_disclosure"] = "Original graphical technology briefing."
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "ai-news.json"
            config_path.write_text(json.dumps(raw), encoding="utf-8")
            config = load_topic(config_path)
            output = Path(directory) / "metadata.json"
            write_metadata(
                config,
                output,
                Path("clip.mp4"),
                {"generated_at": "2026-11-19T00:00:00+00:00", "sha256": "abc"},
                {"valid": True, "sha256": "abc"},
            )
            payload = json.loads(output.read_text())
        self.assertEqual(payload["content_disclosure"], "Original graphical technology briefing.")

    @patch("trendclip.cli.shutil.which", return_value="/usr/bin/tool")
    @patch(
        "trendclip.cli.render_clip",
        return_value={"generated_at": "2026-11-19T00:00:00+00:00", "sha256": "abc"},
    )
    @patch("trendclip.cli.probe_video", return_value={"valid": True})
    @patch("trendclip.cli.inspect_media_quality", return_value={"valid": True, "errors": []})
    def test_render_command_behavior(self, quality, probe, render, which):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            config_dir = project / "config" / "topics"
            config_dir.mkdir(parents=True)
            (config_dir / "gta6.json").write_text(
                (ROOT / "config" / "topics" / "gta6.json").read_text(), encoding="utf-8"
            )
            output = project / "output"
            def fake_render(config, path):
                path.write_bytes(b"video")
                return {"generated_at": "2026-11-19T00:00:00+00:00", "sha256": "abc"}

            render.side_effect = fake_render
            with patch("trendclip.cli.PROJECT_ROOT", project):
                code = main(
                    [
                        "render",
                        "--topic",
                        "gta6",
                        "--date",
                        "2026-11-19",
                        "--output-root",
                        str(output),
                    ]
                )
        self.assertEqual(code, 0)
        render.assert_called_once()

    @patch("trendclip.cli.shutil.which", return_value="/usr/bin/tool")
    @patch("trendclip.cli.render_clip")
    @patch("trendclip.cli.probe_video", return_value={"valid": False, "errors": ["bad fps"]})
    @patch("trendclip.cli.inspect_media_quality", return_value={"valid": True, "errors": []})
    def test_failed_validation_preserves_prior_export(self, quality, probe, render, which):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            config_dir = project / "config" / "topics"
            config_dir.mkdir(parents=True)
            (config_dir / "gta6.json").write_text(
                (ROOT / "config" / "topics" / "gta6.json").read_text(), encoding="utf-8"
            )
            destination = project / "output" / "gta6" / "2026-11-19"
            destination.mkdir(parents=True)
            prior = {
                "clip-001.mp4": b"prior-video",
                "clip-001.json": b"prior-metadata",
                "validation.json": b"prior-validation",
            }
            for name, content in prior.items():
                (destination / name).write_bytes(content)

            def fake_render(config, path):
                path.write_bytes(b"bad-new-video")
                return {"generated_at": "2026-11-19T00:00:00+00:00", "sha256": "bad"}

            render.side_effect = fake_render
            with patch("trendclip.cli.PROJECT_ROOT", project):
                code = main(
                    [
                        "render",
                        "--topic",
                        "gta6",
                        "--date",
                        "2026-11-19",
                        "--output-root",
                        str(project / "output"),
                    ]
                )
            observed = {name: (destination / name).read_bytes() for name in prior}
        self.assertEqual(code, 2)
        self.assertEqual(observed, prior)

    def test_partial_promotion_failure_rolls_back_all_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            staging = root / "staging"
            destination = root / "destination"
            staging.mkdir()
            destination.mkdir()
            prior = {
                "clip-001.mp4": b"prior-video",
                "clip-001.json": b"prior-metadata",
                "validation.json": b"prior-validation",
            }
            for name, content in prior.items():
                (destination / name).write_bytes(content)
                (staging / name).write_bytes(b"new-" + content)

            real_replace = __import__("os").replace
            calls = 0

            def fail_during_promotion(source, target):
                nonlocal calls
                calls += 1
                if calls == 5:
                    raise OSError("injected promotion failure")
                return real_replace(source, target)

            with patch("trendclip.cli.os.replace", side_effect=fail_during_promotion):
                with self.assertRaises(RenderError):
                    promote_export(staging, destination)
            observed = {name: (destination / name).read_bytes() for name in prior}
        self.assertEqual(observed, prior)

    @patch("trendclip.cli.shutil.which", return_value=None)
    def test_render_command_fails_when_ffmpeg_is_missing(self, which):
        self.assertEqual(main(["render", "--topic", "gta6"]), 1)

    @patch("trendclip.cli.shutil.which", return_value="/usr/bin/tool")
    def test_render_command_rejects_external_config_root(self, which):
        self.assertEqual(
            main(["render", "--topic", "gta6", "--config-root", "/tmp"]),
            1,
        )


if __name__ == "__main__":
    unittest.main()

