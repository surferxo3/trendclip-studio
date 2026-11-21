import json
import tempfile
import unittest
from pathlib import Path

from trendclip.config import ConfigError, load_topic, validate_date, validate_slug


ROOT = Path(__file__).resolve().parent.parent


class ConfigTests(unittest.TestCase):
    def test_loads_gta6_topic(self):
        config = load_topic(ROOT / "config" / "topics" / "gta6.json")
        self.assertEqual(config.slug, "gta6")
        self.assertEqual((config.width, config.height), (1080, 1920))
        self.assertGreaterEqual(len(config.scenes), 2)

    def test_rejects_invalid_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text("not-json", encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_topic(path)

    def test_rejects_unsafe_slug_and_date(self):
        for value in ("../gta6", "GTA 6", ""):
            with self.assertRaises(ConfigError):
                validate_slug(value)
        for value in ("19-11-2026", "2026/11/19", "today", "2026-99-99"):
            with self.assertRaises(ConfigError):
                validate_date(value)

    def test_rejects_wrong_dimensions(self):
        raw = json.loads((ROOT / "config" / "topics" / "gta6.json").read_text(encoding="utf-8"))
        raw["video"]["size"] = [1920, 1080]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(ConfigError, "1080x1920"):
                load_topic(path)

    def test_rejects_unsupported_glyph_and_insecure_source(self):
        raw = json.loads((ROOT / "config" / "topics" / "gta6.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            raw["scenes"][0]["body"] = "UNSUPPORTED EMOJI 😊"
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(ConfigError, "unsupported glyphs"):
                load_topic(path)

            raw = json.loads((ROOT / "config" / "topics" / "gta6.json").read_text(encoding="utf-8"))
            raw["metadata"]["source_references"][0]["url"] = "http://example.com"
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(ConfigError, "HTTPS"):
                load_topic(path)


if __name__ == "__main__":
    unittest.main()

