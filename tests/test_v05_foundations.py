import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from trendclip.codex_adapter import CodexAdapterError, invoke
from trendclip.highlight_strategies import select_moments
from trendclip.jobs import list_jobs, update_job
from trendclip.media_worker import _optional_semantic_rerank
from trendclip.profiles import ProfileError, load_profile, load_profiles
from trendclip.rights import RightsError, validate_rights


ROOT = Path(__file__).resolve().parent.parent


class ProfileTests(unittest.TestCase):
    def test_initial_profiles_are_valid_and_strategy_driven(self):
        profiles = load_profiles(ROOT / "config" / "profiles.json")
        self.assertEqual(len(profiles), 12)
        self.assertEqual(load_profile(ROOT / "config" / "profiles.json", "gta6").strategy, "gaming")
        self.assertEqual(load_profile(ROOT / "config" / "profiles.json", "gaming").strategy, "gaming")
        self.assertEqual(load_profile(ROOT / "config" / "profiles.json", "podcasts-interviews").strategy, "conversation")

    def test_rejects_unknown_profile(self):
        with self.assertRaisesRegex(ProfileError, "unknown profile"):
            load_profile(ROOT / "config" / "profiles.json", "not-real")


class RightsTests(unittest.TestCase):
    def test_unknown_and_research_only_are_hard_blocked(self):
        for category in ("unknown", "research-only"):
            with self.assertRaises(RightsError):
                validate_rights({"category": category, "allowed_platforms": ["youtube"]})

    def test_license_requires_reference_and_is_persistable(self):
        with self.assertRaisesRegex(RightsError, "reference"):
            validate_rights({"category": "licensed", "allowed_platforms": ["youtube"]})
        rights = validate_rights({"category": "licensed", "permission_reference": "License L-42", "allowed_platforms": ["youtube", "tiktok"], "commercial_use_scope": "commercial", "attribution_required": True, "attribution_note": "Source: creator"})
        self.assertEqual(rights["category"], "licensed")
        self.assertIn("confirmed_at", rights)


class StrategyTests(unittest.TestCase):
    def test_each_strategy_returns_explainable_components(self):
        db = np.full(90, -30.0)
        db[40:43] = -4.0
        words = [{"w": word, "s": 39 + index * .7, "e": 39.5 + index * .7} for index, word in enumerate(("why", "this", "is", "important", "but", "actually", "works"))]
        heatmap = [{"start_time": 39, "end_time": 44, "value": 1.0}]
        visual = [{"second": 41, "motion": 1.0}]
        for strategy in ("educational", "conversation", "gaming", "comedy", "craft"):
            picks = select_moments(strategy, words, db, heatmap, 90, visual_signals=visual, top=1)
            self.assertTrue(picks, strategy)
            self.assertEqual(picks[0]["strategy"], strategy)
            self.assertTrue(picks[0]["score_components"])

    def test_gaming_quality_is_bounded_and_explained(self):
        db = np.full(50, -32.0)
        db[18:22] = -3.0
        words = [
            {"w": "Wait!", "s": 17.0, "e": 17.4},
            {"w": "Watch", "s": 17.5, "e": 17.8},
            {"w": "this", "s": 17.9, "e": 18.2},
            {"w": "police", "s": 18.3, "e": 18.8},
            {"w": "chase.", "s": 18.9, "e": 19.4},
            {"w": "Finally", "s": 23.0, "e": 23.5},
            {"w": "we", "s": 23.6, "e": 23.8},
            {"w": "escaped!", "s": 23.9, "e": 24.5},
        ]
        picks = select_moments("gaming", words, db, [], 50, top=1, minimum=7, maximum=20)
        self.assertTrue(picks)
        self.assertLessEqual(picks[0]["quality_score"], 10.0)
        self.assertEqual(picks[0]["quality_components"]["gaming_event"], 1.0)
        self.assertEqual(picks[0]["quality_components"]["payoff"], 1.0)
        self.assertIn("clear payoff language", picks[0]["why"])

    def test_context_dependent_opening_is_flagged(self):
        db = np.full(35, -30.0)
        db[10:13] = -2.0
        words = [
            {"w": "But", "s": 9.0, "e": 9.3},
            {"w": "this", "s": 9.4, "e": 9.7},
            {"w": "car", "s": 9.8, "e": 10.2},
            {"w": "crashed", "s": 10.3, "e": 10.8},
            {"w": "again.", "s": 10.9, "e": 11.4},
        ]
        picks = select_moments("gaming", words, db, [], 35, top=1, minimum=7, maximum=15)
        self.assertTrue(picks)
        self.assertEqual(picks[0]["quality_components"]["clean_start"], 0.0)
        self.assertIn("may depend on earlier context", picks[0]["warnings"])


class JobTests(unittest.TestCase):
    def test_job_history_survives_process_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            update_job(root, "abc123", stage="queued", message="waiting")
            update_job(root, "abc123", stage="ready", message="done")
            jobs = list_jobs(root)
            self.assertEqual(jobs[0]["stage"], "ready")
            self.assertEqual([item["stage"] for item in jobs[0]["history"]], ["queued", "ready"])


class CodexAdapterTests(unittest.TestCase):
    def test_disabled_adapter_never_invokes_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(CodexAdapterError, "disabled"):
                invoke(Path(directory), "semantic-highlight-rerank", {}, enabled=False)

    @patch("trendclip.codex_adapter.availability", return_value={"available": True, "authenticated": True})
    @patch("trendclip.codex_adapter.shutil.which", return_value="/usr/local/bin/codex")
    def test_structured_result_is_validated_and_cached(self, _which, _availability):
        calls = []

        def runner(command, **kwargs):
            calls.append(command)
            output = Path(command[command.index("--output-last-message") + 1])
            output.write_text(json.dumps({"ranked_candidate_ids": ["c2", "c1"], "rationale": "Clearer opening"}), encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, "", "")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = invoke(root, "semantic-highlight-rerank", {"candidates": ["c1", "c2"]}, enabled=True, runner=runner)
            cached = invoke(root, "semantic-highlight-rerank", {"candidates": ["c1", "c2"]}, enabled=True, runner=lambda *args, **kwargs: self.fail("cache miss"))
        self.assertEqual(result, cached)
        self.assertIn("read-only", calls[0])
        self.assertNotIn("danger-full-access", calls[0])

    @patch("trendclip.media_worker.invoke")
    def test_invalid_agent_ranking_falls_back_to_deterministic_order(self, invoke_mock):
        invoke_mock.return_value = {"ranked_candidate_ids": ["2", "2"], "rationale": "invalid duplicate"}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config").mkdir()
            (root / "config" / "settings.json").write_text(json.dumps({"codex": {"enabled": True}}), encoding="utf-8")
            (root / "state" / "jobs" / "abc123").mkdir(parents=True)
            (root / "state" / "media").mkdir(parents=True)
            result = {
                "job_id": "abc123",
                "strategy": "gaming",
                "candidates": [
                    {"n": 1, "start": 1, "end": 10, "text": "first", "score_components": {}},
                    {"n": 2, "start": 11, "end": 20, "text": "second", "score_components": {}},
                ],
            }
            output = _optional_semantic_rerank(root, result)
        self.assertEqual([item["n"] for item in output["candidates"]], [1, 2])
        self.assertEqual(output["codex_assistance"]["fallback"], "deterministic-ranking")


if __name__ == "__main__":
    unittest.main()
