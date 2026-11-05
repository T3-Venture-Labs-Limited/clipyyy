"""Cut each clip out of the source and plan a crop that keeps the speaker's face in frame."""

from __future__ import annotations

import os
import subprocess
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from clipyyy.config import home
from clipyyy.media import ffmpeg_bin, probe, run_ffmpeg

SAMPLE_FPS = 2
MIN_FACE_RATIO = 0.5
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_detector/"
    "blaze_face_short_range/float16/latest/blaze_face_short_range.tflite"
)


@dataclass(slots=True)
class Face:
    x: float
    y: float
    width: float
    height: float


def prepare_clips(source: dict, timeline: dict, work_dir: Path, aspect: float, face_tracking: bool) -> dict:
    prepared = []
    for clip in timeline["clips"]:
        clip_dir = work_dir / f"clip-{clip['rank']:02d}"
        clip_dir.mkdir(parents=True, exist_ok=True)
        speaker_path = clip_dir / "speaker.mp4"
        run_ffmpeg(
            [
                "-ss",
                str(clip["start_seconds"]),
                "-to",
                str(clip["end_seconds"]),
                "-i",
                source["video_path"],
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "18",
                "-an",
                str(speaker_path),
            ]
        )
        if face_tracking:
            plan = plan_crop(speaker_path, aspect)
        else:
            width, height, _ = probe(speaker_path)
            plan = center_plan(width, height, aspect, "face tracking off")
        prepared.append({"rank": clip["rank"], "speaker_path": str(speaker_path), **plan})
    return {"clips": prepared}


def plan_crop(clip_path: Path, aspect: float) -> dict:
    width, height, _ = probe(clip_path)
    samples = sample_faces(clip_path, width, height)
    if not samples:
        return center_plan(width, height, aspect, "face detector unavailable")
    tracked = [(t, f) for t, f in samples if f is not None]
    if len(tracked) / len(samples) < MIN_FACE_RATIO:
        return center_plan(width, height, aspect, f"faces found in {len(tracked)}/{len(samples)} frames")
    centers = smooth([((f.x + f.width / 2) * width, (f.y + f.height / 2) * height) for _, f in tracked])
    boxes = [
        {"t": round(t, 3), **face_box(f, width, height, cx, cy, aspect)}
        for (t, f), (cx, cy) in zip(tracked, centers, strict=True)
    ]
    return {"crop_mode": "face", "crop_boxes": boxes, "note": None}


def center_plan(width: int, height: int, aspect: float, note: str | None) -> dict:
    if width / max(height, 1) > aspect:
        crop_h, crop_w = height, round(height * aspect)
    else:
        crop_w, crop_h = width, round(width / aspect)
    box = {
        "t": 0.0,
        "x": (width - crop_w) // 2,
        "y": (height - crop_h) // 2,
        "width": max(2, crop_w),
        "height": max(2, crop_h),
    }
    return {"crop_mode": "center", "crop_boxes": [box], "note": note}


def face_box(face: Face, width: int, height: int, cx: float, cy: float, aspect: float) -> dict:
    crop_h = max(face.height * height * 3.2, height * 0.45)
    crop_w = crop_h * aspect
    if crop_w > width:
        crop_w, crop_h = float(width), width / aspect
    if crop_h > height:
        crop_h, crop_w = float(height), height * aspect
    x = clamp(cx - crop_w / 2, 0.0, width - crop_w)
    y = clamp(cy - crop_h / 2, 0.0, height - crop_h)
    return {"x": round(x), "y": round(y), "width": round(crop_w), "height": round(crop_h)}


def sample_faces(clip_path: Path, width: int, height: int) -> list[tuple[float, Face | None]]:
    os.environ.setdefault("GLOG_minloglevel", "2")  # silence MediaPipe/LiteRT info logs
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
    try:
        import mediapipe as mp
        import numpy as np
    except ImportError:
        return []
    detector = mp.tasks.vision.FaceDetector.create_from_options(
        mp.tasks.vision.FaceDetectorOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(_model_path())),
            min_detection_confidence=0.5,
        )
    )
    frame_bytes = width * height * 3
    proc = subprocess.Popen(
        [
            ffmpeg_bin(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(clip_path),
            "-vf",
            f"fps={SAMPLE_FPS}",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "pipe:1",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    samples: list[tuple[float, Face | None]] = []
    try:
        assert proc.stdout is not None
        while len(raw := proc.stdout.read(frame_bytes)) == frame_bytes:
            frame = np.frombuffer(raw, dtype=np.uint8).reshape((height, width, 3))
            result = detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=frame))
            faces = [
                Face(
                    d.bounding_box.origin_x / width,
                    d.bounding_box.origin_y / height,
                    d.bounding_box.width / width,
                    d.bounding_box.height / height,
                )
                for d in result.detections
            ]
            samples.append((len(samples) / SAMPLE_FPS, dominant(faces)))
    finally:
        proc.stdout and proc.stdout.close()
        proc.wait()
        detector.close()
    return samples


def dominant(faces: list[Face]) -> Face | None:
    """Largest face, ties broken by closeness to the centre."""
    if not faces:
        return None
    return max(
        faces,
        key=lambda f: (
            f.width * f.height,
            -(((f.x + f.width / 2 - 0.5) ** 2 + (f.y + f.height / 2 - 0.5) ** 2) ** 0.5),
        ),
    )


def smooth(points: list[tuple[float, float]], window: int = 3) -> list[tuple[float, float]]:
    half = window // 2
    result = []
    for i in range(len(points)):
        chunk = points[max(0, i - half) : i + half + 1]
        result.append((sum(p[0] for p in chunk) / len(chunk), sum(p[1] for p in chunk) / len(chunk)))
    return result


def clamp(value: float, low: float, high: float) -> float:
    return low if low > high else max(low, min(high, value))


def _model_path() -> Path:
    path = home() / "models" / "blaze_face_short_range.tflite"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(MODEL_URL, path)
    return path
