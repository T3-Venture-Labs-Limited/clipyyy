"""Assemble the final clips: reframed speaker + optional B-roll, source audio, burned captions."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from clipyyy.captions import ass_filter, clip_words, write_ass
from clipyyy.media import has_audio, probe, run_ffmpeg

FPS = 30
SIZES = {"9:16": (1080, 1920), "4:5": (1080, 1350), "1:1": (1080, 1080)}


def render_clips(
    source: dict,
    selection: dict,
    timeline: dict,
    prepared: dict,
    transcript: dict,
    work_dir: Path,
    out_dir: Path,
    options: dict,
) -> dict:
    width, height = SIZES[options["aspect_ratio"]]
    out_dir.mkdir(parents=True, exist_ok=True)
    prepared_by_rank = {c["rank"]: c for c in prepared["clips"]}
    selected_by_rank = {c["rank"]: c for c in selection["clips"]}
    renders = []
    for clip in timeline["clips"]:
        rank = clip["rank"]
        meta = selected_by_rank[rank]
        output = out_dir / f"clip-{rank:02d}-{slugify(meta['title'])}.mp4"
        clip_dir = work_dir / f"clip-{rank:02d}"
        try:
            render_clip(
                source_video=Path(source["video_path"]),
                clip=clip,
                prepared=prepared_by_rank[rank],
                words=clip_words(transcript, clip["start_seconds"], clip["end_seconds"]),
                work_dir=clip_dir,
                output=output,
                size=(width, height),
                caption_style=options["caption_style"] if options["captions"] else None,
            )
            out_w, out_h, duration = probe(output)
            make_poster(output, min(1.0, duration / 2))
            renders.append(
                {
                    "rank": rank,
                    "status": "ready",
                    "file_path": str(output),
                    "width": out_w,
                    "height": out_h,
                    "duration_seconds": round(duration, 2),
                }
            )
        except Exception as exc:  # one bad clip should not sink the others
            renders.append({"rank": rank, "status": "failed", "error": str(exc)})
        finally:
            shutil.rmtree(clip_dir / "segments", ignore_errors=True)
    if not any(r["status"] == "ready" for r in renders):
        raise RuntimeError("Every clip failed to render: " + "; ".join(r.get("error", "") for r in renders))
    return {"renders": renders}


def render_clip(
    source_video: Path,
    clip: dict,
    prepared: dict,
    words: list[dict],
    work_dir: Path,
    output: Path,
    size: tuple[int, int],
    caption_style: str | None,
) -> None:
    width, height = size
    segments_dir = work_dir / "segments"
    segments_dir.mkdir(parents=True, exist_ok=True)
    speaker = Path(prepared["speaker_path"])

    segment_paths = []
    for window in clip["windows"]:
        segment = segments_dir / f"{window['index']:03d}.mp4"
        if window["type"] == "broll" and window.get("broll_path"):
            args = [
                "-stream_loop",
                "-1",
                "-i",
                window["broll_path"],
                "-t",
                str(window["duration"]),
                "-vf",
                fill_filter(width, height),
            ]
        else:
            box = nearest_box(window["start"], prepared["crop_boxes"])
            args = [
                "-ss",
                str(window["start"]),
                "-to",
                str(window["end"]),
                "-i",
                str(speaker),
                "-vf",
                f"crop={box['width']}:{box['height']}:{box['x']}:{box['y']},"
                f"scale={width}:{height},setsar=1,fps={FPS},format=yuv420p",
            ]
        run_ffmpeg([*args, "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", str(segment)])
        segment_paths.append(segment)

    concat_list = segments_dir / "list.txt"
    concat_list.write_text("".join(f"file '{p.resolve()}'\n" for p in segment_paths), encoding="utf-8")

    inputs = ["-f", "concat", "-safe", "0", "-i", str(concat_list)]
    maps = ["-map", "0:v:0"]
    if has_audio(source_video):
        inputs += [
            "-ss",
            str(clip["start_seconds"]),
            "-to",
            str(clip["end_seconds"]),
            "-i",
            str(source_video),
        ]
        maps += ["-map", "1:a:0", "-c:a", "aac", "-b:a", "160k"]

    if caption_style and words:
        ass_path = write_ass(words, work_dir / "captions.ass", width, height, caption_style)
        video_args = ["-vf", ass_filter(ass_path), "-c:v", "libx264", "-preset", "medium", "-crf", "20"]
    else:
        video_args = ["-c:v", "copy"]

    run_ffmpeg([*inputs, *maps, *video_args, "-shortest", "-movflags", "+faststart", str(output)])


def poster_path(video: Path) -> Path:
    return video.with_suffix(".jpg")


def make_poster(video: Path, at: float) -> None:
    """A still frame for previews in the UI."""
    run_ffmpeg(
        [
            "-ss",
            str(at),
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-vf",
            "scale=540:-2",
            "-q:v",
            "4",
            str(poster_path(video)),
        ]
    )


def fill_filter(width: int, height: int) -> str:
    return (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},"
        f"setsar=1,fps={FPS},format=yuv420p"
    )


def nearest_box(t: float, boxes: list[dict]) -> dict:
    return min(boxes, key=lambda b: abs(b["t"] - t))


def slugify(text: str, limit: int = 40) -> str:
    slug = re.sub(r"[^\w]+", "-", text.lower(), flags=re.UNICODE).strip("-")
    return slug[:limit].rstrip("-") or "clip"
