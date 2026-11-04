"""Render a synthetic video end to end with ffmpeg (no network, no models)."""

import shutil

import pytest

from clipyyy.media import has_audio, probe, run_ffmpeg
from clipyyy.reframe import center_plan
from clipyyy.render import render_clips
from clipyyy.timeline import plan_timeline

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")


@pytest.mark.parametrize("aspect,size", [("9:16", (1080, 1920)), ("1:1", (1080, 1080))])
def test_render_synthetic_clip(tmp_path, transcript, aspect, size):
    source = tmp_path / "source.mp4"
    run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=1280x720:rate=30:duration=40",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=40",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-c:a",
            "aac",
            "-shortest",
            str(source),
        ]
    )
    selection = {"clips": [{"rank": 1, "start_seconds": 6.0, "end_seconds": 23.4, "title": "Test clip"}]}
    timeline = plan_timeline(selection, transcript, broll=False)
    speaker = tmp_path / "work" / "clip-01" / "speaker.mp4"
    speaker.parent.mkdir(parents=True)
    run_ffmpeg(
        [
            "-ss",
            "6",
            "-to",
            "23.4",
            "-i",
            str(source),
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            str(speaker),
        ]
    )
    aspect_value = size[0] / size[1]
    prepared = {
        "clips": [{"rank": 1, "speaker_path": str(speaker), **center_plan(1280, 720, aspect_value, None)}]
    }
    options = {"aspect_ratio": aspect, "captions": True, "caption_style": "bold"}

    result = render_clips(
        {"video_path": str(source)},
        selection,
        timeline,
        prepared,
        transcript,
        tmp_path / "work",
        tmp_path / "out",
        options,
    )

    render = result["renders"][0]
    assert render["status"] == "ready", render.get("error")
    width, height, duration = probe(tmp_path / "out" / "clip-01-test-clip.mp4")
    assert (width, height) == size
    assert abs(duration - 17.4) < 0.5
    assert has_audio(tmp_path / "out" / "clip-01-test-clip.mp4")
    assert (tmp_path / "out" / "clip-01-test-clip.jpg").exists()
