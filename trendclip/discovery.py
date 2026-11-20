"""Read-only feed discovery and evidence-based candidate ranking."""

from __future__ import annotations

import json
import math
import re
import subprocess
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional
from urllib.parse import urlparse
from types import SimpleNamespace

from .config import ConfigError, TopicConfig
from .profiles import NicheProfile


MAX_FEED_BYTES = 2_000_000
TOKEN_RE = re.compile(r"[a-z0-9]+")


class DiscoveryError(RuntimeError):
    pass


@dataclass(frozen=True)
class SourceDefinition:
    name: str
    url: str
    reliability: float
    enabled: bool


@dataclass(frozen=True)
class SourceItem:
    source_name: str
    source_url: str
    title: str
    url: str
    published_at: str
    summary: str
    source_reliability: float


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _child_text(element: ET.Element, names: Iterable[str]) -> str:
    wanted = set(names)
    for child in element:
        if _local_name(child.tag) in wanted and child.text:
            return child.text.strip()
    return ""


def _entry_link(element: ET.Element) -> str:
    for child in element:
        if _local_name(child.tag) != "link":
            continue
        href = child.attrib.get("href", "").strip()
        relation = child.attrib.get("rel", "alternate")
        if href and relation in ("alternate", ""):
            return href
        if child.text and child.text.strip().startswith("http"):
            return child.text.strip()
    return ""


def parse_feed(payload: bytes, source: SourceDefinition) -> List[SourceItem]:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise DiscoveryError(f"{source.name} returned invalid XML: {exc}") from exc
    entries = [node for node in root.iter() if _local_name(node.tag) in ("entry", "item")]
    items: List[SourceItem] = []
    for entry in entries[:100]:
        title = _child_text(entry, ("title",))
        link = _entry_link(entry)
        published = _child_text(entry, ("published", "updated", "pubdate"))
        summary = _child_text(entry, ("summary", "description", "content"))
        if title and link and published:
            items.append(
                SourceItem(
                    source_name=source.name,
                    source_url=source.url,
                    title=title[:500],
                    url=link[:2000],
                    published_at=published[:100],
                    summary=re.sub(r"<[^>]+>", " ", summary)[:2000],
                    source_reliability=source.reliability,
                )
            )
    return items


def _parse_datetime(value: str) -> Optional[datetime]:
    cleaned = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError:
        try:
            from email.utils import parsedate_to_datetime

            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _tokens(value: str) -> set[str]:
    return set(TOKEN_RE.findall(value.lower()))


def score_item(item: SourceItem, topic: TopicConfig, now: datetime) -> Dict[str, object]:
    haystack = _tokens(f"{item.title} {item.summary}")
    keyword_sets = [_tokens(keyword) for keyword in topic.keywords]
    matched = [keyword for keyword, tokens in zip(topic.keywords, keyword_sets) if tokens and tokens <= haystack]
    excluded = [value for value in topic.exclusions if _tokens(value) <= haystack]
    relevance = min(1.0, len(matched) / max(1, min(3, len(topic.keywords))))
    published = _parse_datetime(item.published_at)
    if published is None:
        freshness = 0.0
        age_hours = None
    else:
        age_hours = max(0.0, (now - published).total_seconds() / 3600)
        freshness = math.exp(-age_hours / (24 * 10))
    if excluded:
        relevance = 0.0
    total = 100 * (0.50 * relevance + 0.30 * freshness + 0.20 * item.source_reliability)
    return {
        **asdict(item),
        "score": round(total, 2),
        "score_components": {
            "topic_relevance": round(relevance, 4),
            "freshness": round(freshness, 4),
            "source_reliability": round(item.source_reliability, 4),
            "engagement": None,
            "growth_velocity": None,
        },
        "matched_keywords": matched,
        "excluded_terms": excluded,
        "age_hours": None if age_hours is None else round(age_hours, 2),
        "ranking_disclosure": "No engagement or growth data was available from this feed; score uses relevance, freshness, and source reliability only.",
    }


def load_sources(path: Path) -> tuple[List[str], List[SourceDefinition]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"cannot load source configuration: {exc}") from exc
    hosts = raw.get("allowed_hosts")
    sources = raw.get("sources")
    if not isinstance(hosts, list) or not hosts or not all(isinstance(host, str) for host in hosts):
        raise ConfigError("allowed_hosts must be a non-empty string list")
    if not isinstance(sources, list) or not sources:
        raise ConfigError("sources must be a non-empty list")
    result = []
    for index, value in enumerate(sources):
        if not isinstance(value, dict):
            raise ConfigError(f"source {index} must be an object")
        url = value.get("url")
        name = value.get("name")
        reliability = value.get("reliability")
        enabled = value.get("enabled", True)
        parsed = urlparse(url) if isinstance(url, str) else None
        if not isinstance(name, str) or not name.strip():
            raise ConfigError(f"source {index} needs a name")
        if not parsed or parsed.scheme != "https" or parsed.hostname not in hosts:
            raise ConfigError(f"source {index} must use HTTPS and an allowed host")
        if not isinstance(reliability, (int, float)) or not 0 <= reliability <= 1:
            raise ConfigError(f"source {index} reliability must be between 0 and 1")
        if not isinstance(enabled, bool):
            raise ConfigError(f"source {index} enabled must be boolean")
        result.append(SourceDefinition(name.strip(), url, float(reliability), enabled))
    return list(hosts), result


def _download(url: str, allowed_hosts: List[str], timeout: int = 12) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "TrendClip-Studio/0.2 (+local-read-only-discovery)"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            final = urlparse(response.geturl())
            if final.scheme != "https" or final.hostname not in allowed_hosts:
                raise DiscoveryError("source redirected outside the approved host allowlist")
            payload = response.read(MAX_FEED_BYTES + 1)
    except (OSError, urllib.error.URLError) as exc:
        raise DiscoveryError(f"could not retrieve approved feed: {exc}") from exc
    if len(payload) > MAX_FEED_BYTES:
        raise DiscoveryError("feed exceeds the 2 MB safety limit")
    return payload


def discover(
    topic: TopicConfig,
    source_path: Path,
    *,
    now: Optional[datetime] = None,
    downloader: Callable[[str, List[str]], bytes] = _download,
) -> Dict[str, object]:
    allowed_hosts, sources = load_sources(source_path)
    timestamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    collected: List[SourceItem] = []
    errors = []
    for source in sources:
        if not source.enabled:
            continue
        try:
            collected.extend(parse_feed(downloader(source.url, allowed_hosts), source))
        except DiscoveryError as exc:
            errors.append({"source": source.name, "error": str(exc)})
    unique: Dict[str, SourceItem] = {}
    for item in collected:
        unique.setdefault(item.url, item)
    ranked = [score_item(item, topic, timestamp) for item in unique.values()]
    ranked = [item for item in ranked if item["score_components"]["topic_relevance"] > 0]
    ranked.sort(key=lambda item: item["score"], reverse=True)
    return {
        "topic": topic.slug,
        "generated_at": timestamp.isoformat(),
        "candidate_count": len(ranked),
        "candidates": ranked,
        "source_errors": errors,
        "measurement_limits": "Feed discovery does not prove social-media trend status. Engagement and growth fields remain null unless an approved source supplies real values.",
    }


def save_report(report: Dict[str, object], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(destination)


def _ytdlp_json(url: str, extra: Optional[List[str]] = None, *, timeout: int = 60) -> Dict[str, object]:
    command = [sys.executable, "-m", "yt_dlp", "--no-warnings", "--no-progress", "--no-playlist", "-J"]
    command.extend(extra or [])
    command.append(url)
    completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if completed.returncode != 0:
        raise DiscoveryError((completed.stderr or completed.stdout or "YouTube discovery failed")[-900:].strip())
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise DiscoveryError("YouTube discovery returned invalid metadata") from exc


def discover_youtube_trends(
    topic: TopicConfig,
    *,
    now: Optional[datetime] = None,
    hours: float = 48,
    limit: int = 24,
    minimum_token_matches: int = 2,
) -> Dict[str, object]:
    """Search recent YouTube uploads and rank them by observed views per hour."""
    if not 1 <= hours <= 720 or not 1 <= limit <= 50 or not 1 <= minimum_token_matches <= 3:
        raise DiscoveryError("trend search bounds are invalid")
    timestamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    query = topic.topic_name.replace(" ", "+")
    search_url = f"https://www.youtube.com/results?search_query={query}&sp=CAI%253D"
    flat = _ytdlp_json(search_url, ["--flat-playlist", "--playlist-end", str(limit)])
    urls = []
    flat_by_url = {}
    for entry in flat.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        value = entry.get("url")
        if isinstance(value, str) and value.startswith("http"):
            urls.append(value)
            flat_by_url[value] = entry

    def detail(url: str):
        try:
            return _ytdlp_json(url, ["--skip-download"], timeout=20)
        except (DiscoveryError, subprocess.TimeoutExpired) as exc:
            fallback = dict(flat_by_url.get(url) or {})
            fallback["webpage_url"] = url
            fallback["_detail_error"] = str(exc)
            return fallback

    with ThreadPoolExecutor(max_workers=3) as executor:
        details = [item for item in executor.map(detail, urls) if item]
    rows = []
    detail_errors = []
    topic_tokens = set().union(*(_tokens(keyword) for keyword in topic.keywords))
    exclusion_tokens = [_tokens(value) for value in topic.exclusions]
    for info in details:
        if info.get("is_live"):
            continue
        published_value = info.get("timestamp") or info.get("release_timestamp")
        published = datetime.fromtimestamp(float(published_value), timezone.utc) if published_value else None
        age = max(0.25, (timestamp - published).total_seconds() / 3600) if published else None
        if age is not None and age > hours:
            continue
        title = str(info.get("title") or "").strip()
        relevance_tokens = _tokens(f"{title} {info.get('description') or ''}")
        title_tokens = _tokens(title)
        if not title or len(topic_tokens & relevance_tokens) < minimum_token_matches:
            continue
        if any(tokens and tokens <= title_tokens for tokens in exclusion_tokens):
            continue
        views = int(info.get("view_count") or 0)
        views_per_hour = None if age is None else views / age
        webpage_url = str(info.get("webpage_url") or "")
        if urlparse(webpage_url).hostname not in ("www.youtube.com", "youtube.com", "youtu.be"):
            continue
        thumbnails = info.get("thumbnails") or []
        fallback_thumbnail = thumbnails[-1].get("url") if thumbnails and isinstance(thumbnails[-1], dict) else ""
        rows.append({
            "source_name": str(info.get("channel") or info.get("uploader") or "YouTube"),
            "source_url": search_url,
            "title": title[:500],
            "url": webpage_url[:2000],
            "published_at": "" if published is None else published.isoformat(),
            "summary": str(info.get("description") or "")[:1000],
            "source_reliability": 0.6,
            "views": views,
            "views_per_hour": None if views_per_hour is None else round(views_per_hour, 2),
            "duration": info.get("duration"),
            "thumbnail": str(info.get("thumbnail") or fallback_thumbnail or "")[:2000],
            "has_replay_heatmap": bool(info.get("heatmap")),
            "age_hours": None if age is None else round(age, 2),
            "discovery_kind": "youtube-trend-search" if age is not None else "youtube-recent-search-partial-metadata",
            "metadata_status": "verified" if age is not None else "partial",
        })
        if info.get("_detail_error"):
            detail_errors.append({"source": str(info.get("title") or webpage_url)[:160], "error": "Detailed upload time was temporarily unavailable; showing safe search metadata."})
    rows.sort(key=lambda item: (item["views_per_hour"] is not None, item["views_per_hour"] or 0, item["views"]), reverse=True)
    for item in rows:
        item["rank_value"] = item["views_per_hour"] if item["views_per_hour"] is not None else item["views"]
        item["rank_metric"] = "observed_views_per_hour" if item["views_per_hour"] is not None else "observed_views_partial_metadata"
        item["score_components"] = {
            "topic_relevance": None,
            "freshness": None,
            "source_reliability": item["source_reliability"],
            "engagement": item["views"],
            "growth_velocity": item["views_per_hour"],
        }
        item["matched_keywords"] = []
        item["excluded_terms"] = []
        item["ranking_disclosure"] = "Ranked by observed YouTube views divided by hours since publication. Counts are point-in-time estimates." if item["views_per_hour"] is not None else "Returned by YouTube's recent-search ordering. View count is observed, but exact upload time was temporarily unavailable, so no views-per-hour value was calculated."
    return {
        "topic": topic.slug,
        "generated_at": timestamp.isoformat(),
        "candidate_count": len(rows),
        "candidates": rows,
        "source_errors": detail_errors,
        "measurement_limits": "YouTube search results and view counts are point-in-time observations. Candidates without a verified upload timestamp remain visibly unranked by velocity rather than receiving an invented score.",
    }


def discover_youtube_profile(
    profile: NicheProfile,
    *,
    query: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Dict[str, object]:
    """Discover a configured niche while preserving transparent view-velocity ranking."""
    search = (query or profile.query).strip()
    if not search or len(search) > 160:
        raise DiscoveryError("search query must be between 1 and 160 characters")
    compatible = SimpleNamespace(
        slug=profile.slug,
        topic_name=search,
        keywords=list(profile.keywords),
        exclusions=list(profile.exclusions),
    )
    report = discover_youtube_trends(
        compatible,
        now=now,
        hours=profile.discovery.hours,
        limit=profile.discovery.limit,
        minimum_token_matches=1,
    )
    filtered = []
    allowed_channels = {channel.casefold() for channel in profile.discovery.channels}
    for candidate in report["candidates"]:
        duration = candidate.get("duration")
        if not isinstance(duration, (int, float)) or not profile.discovery.min_duration <= duration <= profile.discovery.max_duration:
            continue
        if allowed_channels and str(candidate.get("source_name", "")).casefold() not in allowed_channels:
            continue
        candidate["profile"] = profile.slug
        candidate["strategy"] = profile.strategy
        candidate["rights_status"] = "unknown"
        candidate["platform"] = "youtube"
        filtered.append(candidate)
    report.update({"topic": profile.slug, "profile": profile.as_dict(), "query": search, "candidates": filtered, "candidate_count": len(filtered)})
    return report


def inspect_youtube_url(profile: NicheProfile, url: str, *, now: Optional[datetime] = None) -> Dict[str, object]:
    """Normalize one user-supplied YouTube URL without downloading its media."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ("www.youtube.com", "youtube.com", "m.youtube.com", "youtu.be"):
        raise DiscoveryError("manual source must be an HTTPS YouTube URL")
    info = _ytdlp_json(url, ["--skip-download"], timeout=60)
    if info.get("is_live"):
        raise DiscoveryError("live sources are not supported by this workflow")
    duration = float(info.get("duration") or 0)
    if not profile.discovery.min_duration <= duration <= profile.discovery.max_duration:
        raise DiscoveryError("source duration is outside this niche's configured limits")
    timestamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    published_value = info.get("timestamp") or info.get("release_timestamp")
    age = None
    if published_value:
        age = max(.25, (timestamp - datetime.fromtimestamp(float(published_value), timezone.utc)).total_seconds() / 3600)
    views = int(info.get("view_count") or 0)
    return {
        "source_name": str(info.get("channel") or info.get("uploader") or "YouTube"),
        "source_url": url,
        "title": str(info.get("title") or "Untitled YouTube source")[:500],
        "url": str(info.get("webpage_url") or url)[:2000],
        "published_at": "" if not published_value else datetime.fromtimestamp(float(published_value), timezone.utc).isoformat(),
        "summary": str(info.get("description") or "")[:1000],
        "views": views,
        "views_per_hour": None if age is None else round(views / age, 2),
        "duration": duration,
        "thumbnail": str(info.get("thumbnail") or "")[:2000],
        "age_hours": None if age is None else round(age, 2),
        "discovery_kind": "manual-youtube-url",
        "ranking_disclosure": "Manually supplied source; it was not promoted by the discovery ranking.",
        "profile": profile.slug,
        "strategy": profile.strategy,
        "rights_status": "unknown",
        "platform": "youtube",
    }


def discover_with_trends(topic: TopicConfig, source_path: Path) -> Dict[str, object]:
    """Prefer recent view-velocity trends and retain official-feed items as fallback."""
    official = discover(topic, source_path)
    errors = list(official.get("source_errors", []))
    try:
        trends = discover_youtube_trends(topic)
    except (DiscoveryError, subprocess.TimeoutExpired, OSError) as exc:
        trends = {"candidates": [], "source_errors": []}
        errors.append({"source": "YouTube trend search", "error": str(exc)})
    combined = []
    seen = set()
    for candidate in list(trends.get("candidates", [])) + list(official.get("candidates", [])):
        url = candidate.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        combined.append(candidate)
    return {
        "topic": topic.slug,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate_count": len(combined),
        "candidates": combined,
        "source_errors": errors,
        "measurement_limits": trends.get("measurement_limits") if trends.get("candidates") else official.get("measurement_limits"),
    }

