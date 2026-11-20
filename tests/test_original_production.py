import json
import tempfile
import unittest
from pathlib import Path

from trendclip.original_production import parse_vtt, split_cues, write_srt


class OriginalProductionTests(unittest.TestCase):
    def test_vtt_to_srt_preserves_timing_and_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vtt = root / "captions.vtt"
            vtt.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:02.500\nHello world\n", encoding="utf-8")
            cues = parse_vtt(vtt)
            write_srt(cues, root / "captions.srt")
            self.assertEqual(cues[0]["text"], "Hello world")
            self.assertIn("00:00:01,000 --> 00:00:02,500", (root / "captions.srt").read_text())

    def test_experiment_scene_weights_are_complete(self):
        root = Path(__file__).resolve().parent.parent
        config = json.loads((root / "productions" / "experiment-001-agentic-commerce" / "production.json").read_text())
        self.assertEqual(len(config["scenes"]), 8)
        self.assertAlmostEqual(sum(scene["weight"] for scene in config["scenes"]), 1.0)
        self.assertEqual(config["title"], "Can AI Spend Your Money Without You Knowing?")

    def test_long_captions_are_split_for_mobile_legibility(self):
        cues = split_cues([{"start": 0.0, "end": 4.0, "text": "one two three four five six seven eight nine ten"}])
        self.assertEqual(len(cues), 2)
        self.assertLessEqual(max(len(str(cue["text"]).split()) for cue in cues), 7)
        self.assertEqual(cues[-1]["end"], 4.0)


if __name__ == "__main__":
    unittest.main()
