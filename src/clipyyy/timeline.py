"""Split each clip into short windows and decide which ones show B-roll instead of the speaker."""

from __future__ import annotations

import re

MIN_WINDOW = 1.5
MAX_WINDOW = 4.0
TARGET_WINDOW = 3.0
MAX_CONSECUTIVE_BROLL = 8.0

STOP_WORDS = frozenset(
    """a an the is are was were be been being have has had do does did will would could should may
    might shall can i you he she it we they me him her us them my your his its our their this that
    these those and or but if then so because as of in on at to for with from by about into over
    after before up down out off not no yes just very really also too more most some any all what
    which who whom whose when where why how there here than like get got go going gonna know think
    mean thing things something anything everything one two well right okay yeah oh um uh actually
    basically literally people want said say says see let lets dont doesnt didnt cant wont im youre
    thats theres""".split()
)


def plan_timeline(selection: dict, transcript: dict, broll: bool) -> dict:
    words = transcript.get("words", [])
    clips = []
    for clip in selection["clips"]:
        start, end = float(clip["start_seconds"]), float(clip["end_seconds"])
        duration = round(end - start, 3)
        sentence_ends = sorted(
            {
                round(min(s["end"], end) - start, 3)
                for s in transcript.get("sentences", [])
                if s["end"] > start and s["start"] < end and min(s["end"], end) - start > 0
            }
        )
        windows = build_windows(duration, sentence_ends)
        clips.append(
            {
                "rank": clip["rank"],
                "start_seconds": start,
                "end_seconds": end,
                "duration_seconds": duration,
                "windows": assign_windows(windows, start, words, broll, clip.get("broll_queries") or []),
            }
        )
    return {"clips": clips}


def build_windows(duration: float, sentence_ends: list[float]) -> list[tuple[float, float]]:
    if duration <= MAX_WINDOW:
        return [(0.0, round(duration, 3))]
    windows: list[tuple[float, float]] = []
    cursor = 0.0
    while duration - cursor > MAX_WINDOW:
        lower, upper = cursor + MIN_WINDOW, cursor + MAX_WINDOW
        candidates = [b for b in sentence_ends if lower <= b <= upper]
        boundary = (
            min(candidates, key=lambda b: (abs(b - (cursor + TARGET_WINDOW)), b)) if candidates else upper
        )
        windows.append((round(cursor, 3), round(boundary, 3)))
        cursor = boundary
    remainder = duration - cursor
    if remainder < MIN_WINDOW and windows:
        prev_start, _ = windows.pop()
        merged = duration - prev_start
        if merged <= MAX_WINDOW:
            windows.append((prev_start, round(duration, 3)))
        else:
            split = round(prev_start + min(MAX_WINDOW, merged - MIN_WINDOW), 3)
            windows.extend([(prev_start, split), (split, round(duration, 3))])
    else:
        windows.append((round(cursor, 3), round(duration, 3)))
    return windows


def assign_windows(
    windows: list[tuple[float, float]],
    clip_start: float,
    words: list[dict],
    broll: bool,
    queries: list[str] | None = None,
) -> list[dict]:
    """Speaker on the first and last window; B-roll on a 2-of-3 cadence, capped at 8s in a row."""
    result = []
    queries = list(queries or [])
    consecutive = 0.0
    for index, (local_start, local_end) in enumerate(windows):
        duration = round(local_end - local_start, 3)
        text = " ".join(
            w["word"]
            for w in words
            if w["end"] > clip_start + local_start and w["start"] < clip_start + local_end
        )
        keywords = extract_keywords(text)
        is_broll = (
            broll
            and 0 < index < len(windows) - 1
            and index % 3 in (1, 2)
            and bool(queries or keywords)
            and consecutive + duration <= MAX_CONSECUTIVE_BROLL
        )
        consecutive = consecutive + duration if is_broll else 0.0
        result.append(
            {
                "index": index,
                "type": "broll" if is_broll else "speaker",
                "start": round(local_start, 3),
                "end": round(local_end, 3),
                "duration": duration,
                "text": text,
                "query": _next_query(queries, keywords) if is_broll else None,
            }
        )
    return result


def _next_query(queries: list[str], keywords: list[str]) -> str:
    """Use the model's visual queries in order, then fall back to transcript keywords."""
    if queries:
        query = queries.pop(0)
        queries.append(query)
        return query
    return " ".join(keywords)


def extract_keywords(text: str, limit: int = 3) -> list[str]:
    words = re.findall(r"[^\W\d_]+(?:'[^\W\d_]+)?", text.lower())
    seen: list[str] = []
    for word in words:
        if len(word) > 3 and word.replace("'", "") not in STOP_WORDS and word not in seen:
            seen.append(word)
    return sorted(seen, key=len, reverse=True)[:limit]
