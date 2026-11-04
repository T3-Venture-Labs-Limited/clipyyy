"""Ask an LLM for the best clips, then snap them to sentence boundaries and validate."""

from __future__ import annotations

import logging
import re
from string import Template
from typing import Any

from clipyyy.config import PACKAGE_DIR
from clipyyy.llm import LLM, LLMError

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "clips": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "rank": {"type": "integer"},
                    "start_seconds": {"type": "number"},
                    "end_seconds": {"type": "number"},
                    "title": {"type": "string"},
                    "post_title": {"type": "string"},
                    "caption": {"type": "string"},
                    "hashtags": {"type": "array", "items": {"type": "string"}},
                    "broll_queries": {"type": "array", "items": {"type": "string"}},
                    "rationale": {"type": "string"},
                    "hook_score": {"type": "number"},
                    "value_score": {"type": "number"},
                    "clarity_score": {"type": "number"},
                    "overall_score": {"type": "number"},
                },
                "required": [
                    "rank",
                    "start_seconds",
                    "end_seconds",
                    "title",
                    "post_title",
                    "caption",
                    "hashtags",
                    "broll_queries",
                    "rationale",
                    "hook_score",
                    "value_score",
                    "clarity_score",
                    "overall_score",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["clips"],
    "additionalProperties": False,
}


def build_prompt(source: dict, transcript: dict, options: dict) -> tuple[str, str]:
    instructions = (options.get("instructions") or "").strip()
    template = Template((PACKAGE_DIR / "prompts" / "clip_selection.md").read_text(encoding="utf-8"))
    system = template.substitute(
        clip_count=options["clip_count"],
        min_seconds=_fmt(options["min_seconds"]),
        max_seconds=_fmt(options["max_seconds"]),
        instructions=f"\nInstructions from the user:\n{instructions}\n" if instructions else "",
    )
    lines = "\n".join(f"[{s['start']:.1f}-{s['end']:.1f}] {s['text']}" for s in transcript["sentences"])
    user = (
        f"Video: {source.get('title') or 'Untitled'}"
        + (f" by {source['uploader']}" if source.get("uploader") else "")
        + f" ({source.get('duration_seconds', 0):.0f}s, language: {transcript.get('language')})\n\n"
        f"Transcript (one sentence per line, [start-end] in seconds):\n{lines}\n\n"
        f"Return up to {options['clip_count']} clips as JSON."
    )
    return system, user


def select_clips(llm: LLM, source: dict, transcript: dict, options: dict) -> dict:
    if not transcript.get("sentences"):
        raise ValueError("No speech found in the video, so there is nothing to clip")
    system, user = build_prompt(source, transcript, options)
    last_error = "no clips returned"
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            raw = llm.complete_json(system, user, SCHEMA, "clip_selection").get("clips", [])
        except LLMError as exc:
            if attempt == MAX_ATTEMPTS:
                raise
            last_error = str(exc)
            logger.warning("clip selection attempt %d failed: %s", attempt, exc)
            continue
        clips = validate_clips(raw, transcript, options)
        if clips:
            return {"model": llm.model, "clips": clips}
        last_error = f"none of the {len(raw)} suggested clips fit the length limits"
        logger.warning("clip selection attempt %d: %s", attempt, last_error)
    raise ValueError(f"Clip selection failed after {MAX_ATTEMPTS} attempts: {last_error}")


def validate_clips(raw_clips: list[dict], transcript: dict, options: dict) -> list[dict]:
    """Snap to sentences, drop clips outside the length range or overlapping a better one."""
    min_s, max_s = float(options["min_seconds"]), float(options["max_seconds"])
    sentences = sorted(transcript["sentences"], key=lambda s: (s["start"], s["end"]))
    accepted: list[dict] = []
    for item in sorted(raw_clips, key=lambda c: _num(c.get("rank"), 999)):
        try:
            start, end = float(item["start_seconds"]), float(item["end_seconds"])
        except (KeyError, TypeError, ValueError):
            continue
        start, end = snap(start, end, sentences, min_s, max_s)
        if not (min_s - 0.5 <= end - start <= max_s + 0.5):
            continue
        if any(start < c["end_seconds"] and c["start_seconds"] < end for c in accepted):
            continue
        hashtags, caption = clean_hashtags(item.get("hashtags"), str(item.get("caption", "")))
        accepted.append(
            {
                "start_seconds": round(start, 3),
                "end_seconds": round(end, 3),
                "title": str(item.get("title", "")).strip() or f"Clip {len(accepted) + 1}",
                "post_title": str(item.get("post_title", "")).strip()[:100],
                "caption": clean_caption(caption),
                "hashtags": hashtags,
                "broll_queries": [
                    str(q).strip() for q in (item.get("broll_queries") or []) if str(q).strip()
                ][:8],
                "rationale": str(item.get("rationale", "")).strip(),
                "score": _num(item.get("overall_score"), 0.0),
                "transcript": excerpt(start, end, sentences),
            }
        )
        if len(accepted) == options["clip_count"]:
            break
    for rank, clip in enumerate(accepted, start=1):
        clip["rank"] = rank
    return accepted


def snap(start: float, end: float, sentences: list[dict], min_s: float, max_s: float) -> tuple[float, float]:
    """Move start/end to the nearest sentence boundaries, then grow or trim into range."""
    if not sentences:
        return start, min(max(end, start + min_s), start + max_s)
    start = min(sentences, key=lambda s: abs(s["start"] - start))["start"]
    end = min(sentences, key=lambda s: abs(s["end"] - end))["end"]
    if end <= start:
        later = [s["end"] for s in sentences if s["end"] > start]
        end = later[0] if later else start + min_s
    if end - start < min_s:
        longer = [s["end"] for s in sentences if s["end"] >= start + min_s]
        if longer:
            end = min(longer)
        else:
            earlier = [s["start"] for s in sentences if s["start"] <= end - min_s]
            if earlier:
                start = max(earlier)
    if end - start > max_s:
        fitting = [s["end"] for s in sentences if start < s["end"] <= start + max_s]
        end = max(fitting) if fitting and max(fitting) - start >= min_s else start + max_s
    return start, end


def excerpt(start: float, end: float, sentences: list[dict]) -> str:
    return " ".join(s["text"] for s in sentences if s["start"] >= start - 0.01 and s["end"] <= end + 0.01)


_LENGTH_MARKER = re.compile(r"\s*\(\d+\s*(?:chars?|characters?|s|secs?|seconds?)\)\s*$", re.IGNORECASE)
_TRAILING_TAGS = re.compile(r"(?:\s*#[\w\u00C0-\uFFFF]+)+\s*$")


def clean_caption(caption: str) -> str:
    value = caption.strip()
    while (updated := _LENGTH_MARKER.sub("", value).strip()) != value:
        value = updated
    return re.sub(r"\s{2,}", " ", value)


def clean_hashtags(tags: Any, caption: str) -> tuple[list[str], str]:
    """Normalise hashtags and move any trailing hashtags out of the caption."""
    found = _TRAILING_TAGS.search(caption)
    extra = found.group(0).split() if found else []
    caption = caption[: found.start()].strip() if found else caption
    result: list[str] = []
    for tag in [*(tags if isinstance(tags, list) else []), *extra]:
        cleaned = "#" + re.sub(r"[^\w\u00C0-\uFFFF]", "", str(tag))
        if len(cleaned) > 1 and cleaned.lower() not in {t.lower() for t in result}:
            result.append(cleaned)
    return result[:10], caption


def _num(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _fmt(value: float) -> str:
    return f"{float(value):g}"
