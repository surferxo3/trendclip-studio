import unittest

from trendclip.export_package import _platform_metadata


class ExportMetadataTests(unittest.TestCase):
    def test_only_selected_destinations_are_generated(self):
        result = _platform_metadata("A GTA 6 moment", "Credit: creator", "gta6", {"youtube", "tiktok"})
        self.assertEqual(set(result), {"youtube", "tiktok"})
        self.assertIn("#GTA6", result["youtube"]["hashtags"])
        self.assertIn("#Shorts", result["youtube"]["hashtags"])
        self.assertIn("Credit: creator", result["tiktok"]["caption"])


if __name__ == "__main__":
    unittest.main()
