"""Optional B-roll from Pexels. Windows without a match fall back to the speaker."""

from __future__ import annotations

import logging
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

FALLBACK_QUERIES = ["city", "nature", "people", "technology", "abstract"]


def fill_broll(timeline: dict, work_dir: Path, api_key: str, orientation: str) -> dict:
    """Download a unique stock video for every B-roll window; returns the updated timeline."""
    windows = [w for clip in timeline["clips"] for w in clip["windows"] if w["type"] == "broll"]
    if not windows:
        return timeline
    if not api_key:
        logger.info("B-roll requested but no Pexels key is set; using the speaker instead")
        return _without_broll(timeline, "no Pexels API key")

    used: set[int] = set()
    with httpx.Client(timeout=60, headers={"Authorization": api_key}) as client:
        for clip in timeline["clips"]:
            for window in clip["windows"]:
                if window["type"] != "broll":
                    continue
                video = _find(client, window["query"], window["duration"], orientation, used)
                if video is None:
                    window.update(type="speaker", note="no stock match")
                    continue
                used.add(video["id"])
                path = work_dir / f"broll-{clip['rank']:02d}-{window['index']:02d}.mp4"
                _download(video["url"], path)
                window.update(
                    broll_path=str(path),
                    broll_credit=f"Video by {video['author']} on Pexels",
                    broll_page=video["page"],
                )
    return timeline


def _find(client: httpx.Client, query: str, duration: float, orientation: str, used: set[int]) -> dict | None:
    for q in [query, *FALLBACK_QUERIES]:
        for min_duration in (duration, 3.0):
            for video in _search(client, q, orientation):
                if video["id"] not in used and video["duration"] >= min_duration:
                    return video
    return None


def _search(client: httpx.Client, query: str, orientation: str) -> list[dict]:
    try:
        response = client.get(
            "https://api.pexels.com/videos/search",
            params={"query": query, "orientation": orientation, "per_page": 15},
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("Pexels search failed for %r: %s", query, exc)
        return []
    results = []
    for item in response.json().get("videos", []):
        files = sorted(
            (f for f in item.get("video_files", []) if f.get("link") and f.get("width")),
            key=lambda f: (abs(int(f["width"]) - 1080), -int(f["width"])),
        )
        if files:
            results.append(
                {
                    "id": item["id"],
                    "duration": float(item.get("duration") or 0),
                    "url": files[0]["link"],
                    "author": (item.get("user") or {}).get("name", "Pexels"),
                    "page": item.get("url", ""),
                }
            )
    return results


def _download(url: str, path: Path) -> None:
    with httpx.stream("GET", url, follow_redirects=True, timeout=120) as response:
        response.raise_for_status()
        with path.open("wb") as fh:
            for chunk in response.iter_bytes():
                fh.write(chunk)


def _without_broll(timeline: dict, note: str) -> dict:
    for clip in timeline["clips"]:
        for window in clip["windows"]:
            if window["type"] == "broll":
                window.update(type="speaker", note=note)
    return timeline
