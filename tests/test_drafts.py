import unittest

from trendclip.drafts import assemble_drafts, editorial_issues, editorial_summary


class DraftAssemblyTests(unittest.TestCase):
    def setUp(self):
        self.candidates = [
            {"n": 1, "quality_score": 9.0, "score": 3.0, "duration": 28, "score_components": {"loudness": .2, "heat": .1}},
            {"n": 2, "quality_score": 7.0, "score": 4.0, "duration": 24, "score_components": {"loudness": .9, "heat": .8, "motion": .7}},
            {"n": 3, "quality_score": 8.0, "score": 2.0, "duration": 15, "score_components": {"loudness": .3}},
            {"n": 4, "quality_score": 5.0, "score": 1.0, "duration": 18, "score_components": {}},
        ]

    def test_builds_three_unique_purposeful_drafts(self):
        drafts = assemble_drafts(self.candidates)
        self.assertEqual([item["kind"] for item in drafts], ["best-story", "high-energy", "quick-hit"])
        self.assertEqual([item["candidate_n"] for item in drafts], [1, 2, 3])
        self.assertEqual(len({item["candidate_n"] for item in drafts}), 3)
        self.assertEqual([item["layout"] for item in drafts], ["balanced", "punch", "clean"])
        self.assertTrue(drafts[0]["recommended"])

    def test_semantic_preference_controls_recommended_draft(self):
        drafts = assemble_drafts(self.candidates, preferred_n=3)
        self.assertEqual(drafts[0]["candidate_n"], 3)
        self.assertTrue(drafts[0]["recommended"])

    def test_empty_input_has_no_placeholder_drafts(self):
        self.assertEqual(assemble_drafts([]), [])

    def test_weak_candidate_is_not_presented_as_best_story(self):
        weak = {
            "n": 1,
            "quality_score": 4.4,
            "score": 1.126,
            "quality_components": {"clean_start": 1.0, "clean_end": 1.0, "hook": 0.0, "payoff": 0.0, "gaming_event": 0.0},
        }
        self.assertEqual(assemble_drafts([weak]), [])
        self.assertIn("no clear hook", " ".join(editorial_issues(weak)))
        summary = editorial_summary([weak])
        self.assertEqual(summary["editorial_status"], "no-suitable-moment")
        self.assertIn("Try another source", summary["editorial_message"])

    def test_story_reason_matches_available_evidence(self):
        hooked = {
            "n": 1,
            "quality_score": 7.6,
            "score": 2.0,
            "quality_components": {"clean_start": 1.0, "clean_end": 1.0, "hook": 1.0, "payoff": 0.0, "gaming_event": 1.0},
        }
        draft = assemble_drafts([hooked])[0]
        self.assertIn("hook and gaming event", draft["reason"])
        self.assertNotIn("hook-to-payoff", draft["reason"])


if __name__ == "__main__":
    unittest.main()
