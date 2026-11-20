import unittest

from trendclip.drafts import assemble_drafts


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


if __name__ == "__main__":
    unittest.main()
