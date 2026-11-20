import json
import tempfile
import unittest
from pathlib import Path

from trendclip.benchmark import BenchmarkError, score_manifest


class BenchmarkTests(unittest.TestCase):
    def _manifest(self):
        return {
            "schema_version": 1,
            "platforms": {"windows": True, "macos": True, "linux": True},
            "samples": [{
                "id": "approved-sample",
                "reviewer_count": 2,
                "metrics": {
                    "top_three_useful": True,
                    "narrative_complete": True,
                    "boundary_caption_accurate": True,
                    "visual_framing_good": True,
                    "technical_reliable": True,
                    "first_time_usable": True,
                    "explainability_good": True,
                },
                "critical_failures": [],
            }],
        }

    def _score(self, value):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "benchmark.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            return score_manifest(path)

    def test_perfect_evidence_scores_ten(self):
        result = self._score(self._manifest())
        self.assertEqual(result["score_out_of_10"], 10.0)
        self.assertTrue(result["perfect_evidence"])
        self.assertTrue(result["release_ready"])

    def test_critical_failure_blocks_release_even_with_high_metrics(self):
        manifest = self._manifest()
        manifest["samples"][0]["critical_failures"] = ["silent accepted export"]
        result = self._score(manifest)
        self.assertEqual(result["score_out_of_10"], 10.0)
        self.assertFalse(result["release_ready"])
        self.assertFalse(result["perfect_evidence"])

    def test_two_reviewers_are_required(self):
        manifest = self._manifest()
        manifest["samples"][0]["reviewer_count"] = 1
        with self.assertRaisesRegex(BenchmarkError, "two reviewers"):
            self._score(manifest)


if __name__ == "__main__":
    unittest.main()
