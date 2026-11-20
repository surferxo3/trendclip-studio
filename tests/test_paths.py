import tempfile
import unittest
from pathlib import Path

from trendclip.paths import UnsafePathError, ensure_within, output_directory


class PathTests(unittest.TestCase):
    def test_output_path_is_nested(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = output_directory(root, root / "output", "gta6", "2026-11-19")
            self.assertEqual(result, (root / "output" / "gta6" / "2026-11-19").resolve())

    def test_rejects_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            with self.assertRaises(UnsafePathError):
                ensure_within(root.parent / "outside", root)


if __name__ == "__main__":
    unittest.main()

