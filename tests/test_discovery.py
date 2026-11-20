import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from trendclip.config import ConfigError, load_topic
from trendclip.discovery import DiscoveryError, SourceDefinition, discover, discover_youtube_trends, load_sources, parse_feed


ROOT = Path(__file__).resolve().parent.parent
ATOM = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Grand Theft Auto VI: Launch Update</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=official"/>
    <published>2026-11-19T08:00:00+00:00</published>
    <summary>Official Rockstar Games update from Vice City and Leonida.</summary>
  </entry>
  <entry>
    <title>Red Dead Online Weekly Update</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=other"/>
    <published>2026-11-19T07:00:00+00:00</published>
    <summary>Unrelated frontier news.</summary>
  </entry>
</feed>"""


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.topic = load_topic(ROOT / "config" / "topics" / "gta6.json")

    def test_parses_atom_feed(self):
        source = SourceDefinition("Official", "https://www.youtube.com/feed.xml", 1.0, True)
        items = parse_feed(ATOM, source)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].title, "Grand Theft Auto VI: Launch Update")

    def test_discovery_ranks_relevant_items_without_invented_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            sources = Path(directory) / "sources.json"
            sources.write_text(
                json.dumps(
                    {
                        "allowed_hosts": ["www.youtube.com"],
                        "sources": [
                            {
                                "name": "Official",
                                "url": "https://www.youtube.com/feed.xml",
                                "reliability": 1.0,
                                "enabled": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            report = discover(
                self.topic,
                sources,
                now=datetime(2026, 11, 19, 12, tzinfo=timezone.utc),
                downloader=lambda url, hosts: ATOM,
            )
        self.assertEqual(report["candidate_count"], 1)
        candidate = report["candidates"][0]
        self.assertIsNone(candidate["score_components"]["engagement"])
        self.assertIsNone(candidate["score_components"]["growth_velocity"])
        self.assertGreater(candidate["score"], 70)

    def test_rejects_source_outside_allowlist(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sources.json"
            path.write_text(
                json.dumps(
                    {
                        "allowed_hosts": ["www.youtube.com"],
                        "sources": [
                            {
                                "name": "Bad",
                                "url": "https://example.com/feed.xml",
                                "reliability": 0.5,
                                "enabled": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ConfigError, "allowed host"):
                load_sources(path)

    @patch("trendclip.discovery._ytdlp_json")
    def test_recent_search_survives_temporary_detail_metadata_failure(self, ytdlp):
        ytdlp.side_effect = [
            {"entries": [{"url": "https://www.youtube.com/watch?v=demo", "title": "Grand Theft Auto VI Update", "description": "Vice City gameplay", "duration": 300, "view_count": 12000, "channel": "Demo", "thumbnails": [{"url": "https://i.ytimg.com/demo.jpg"}]}]},
            DiscoveryError("temporary detail failure"),
        ]
        report = discover_youtube_trends(
            self.topic,
            now=datetime(2026, 11, 20, tzinfo=timezone.utc),
            minimum_token_matches=1,
            limit=1,
        )
        self.assertEqual(report["candidate_count"], 1)
        candidate = report["candidates"][0]
        self.assertIsNone(candidate["views_per_hour"])
        self.assertEqual(candidate["views"], 12000)
        self.assertEqual(candidate["metadata_status"], "partial")
        self.assertEqual(candidate["thumbnail"], "https://i.ytimg.com/demo.jpg")


if __name__ == "__main__":
    unittest.main()

