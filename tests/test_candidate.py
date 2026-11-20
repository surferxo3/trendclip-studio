import unittest
from pathlib import Path

from trendclip.candidate import config_from_candidate
from trendclip.config import load_topic
from trendclip.raster import FONT


ROOT = Path(__file__).resolve().parent.parent


class CandidateVideoTests(unittest.TestCase):
    def test_selected_candidate_changes_video_content_and_metadata(self):
        base = load_topic(ROOT / "config" / "topics" / "gta6.json")
        candidate = {
            "title": "Grand Theft Auto VI Now Available",
            "url": "https://www.youtube.com/shorts/example",
            "source_name": "Rockstar Games — Official YouTube",
            "published_at": "2026-11-19T13:59:56+00:00",
            "score": 67,
        }
        config = config_from_candidate(base, candidate, "2026-11-19")
        rendered_text = " ".join(scene.headline.replace("\n", " ") for scene in config.scenes)
        self.assertIn("NOW AVAILABLE", rendered_text)
        self.assertEqual(config.metadata["selected_candidate"]["url"], candidate["url"])
        self.assertEqual(config.metadata["source_references"][0]["url"], candidate["url"])
        scene_text = "".join(
            scene.eyebrow + scene.headline + scene.body for scene in config.scenes
        )
        self.assertEqual(set(scene_text.upper()) - set(FONT) - {"\n"}, set())


if __name__ == "__main__":
    unittest.main()

