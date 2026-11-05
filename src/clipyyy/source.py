"""Get the source video: download a URL with yt-dlp or take a local file."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

MAX_DURATION_SECONDS = 4 * 60 * 60
VIDEO_FORMAT = "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080][ext=mp4]/bv*[height<=1080]+ba/b"


def is_url(source: str) -> bool:
    return source.startswith(("http://", "https://"))


def fetch_source(source: str, work_dir: Path) -> dict:
    work_dir.mkdir(parents=True, exist_ok=True)
    video_path = work_dir / "source.mp4"
    if is_url(source):
        info = _yt_dlp(["--dump-json", "--skip-download", source])
        if info.get("is_live"):
            raise ValueError("Live streams are not supported")
        duration = float(info.get("duration") or 0)
        if duration > MAX_DURATION_SECONDS:
            raise ValueError(f"Video is {duration / 3600:.1f}h long; the limit is 4h")
        if not video_path.exists():
            _download(source, video_path)
        title, uploader = info.get("title") or source, info.get("uploader") or ""
    else:
        path = Path(source).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"Source file not found: {source}")
        if not video_path.exists():
            _link_or_copy(path, video_path)
        title, uploader = re.sub(r"^[0-9a-f]{12}-", "", path.stem), ""  # strip upload id prefix

    from clipyyy.media import probe

    width, height, duration = probe(video_path)
    if not width:
        raise ValueError("Source has no video stream")
    return {
        "source": source,
        "title": title,
        "uploader": uploader,
        "duration_seconds": duration,
        "width": width,
        "height": height,
        "video_path": str(video_path),
    }


JS_RUNTIMES = ("deno", "node", "bun")


def js_runtime() -> str | None:
    """YouTube needs a JavaScript runtime for its player challenges (yt-dlp EJS)."""
    for name in JS_RUNTIMES:
        path = shutil.which(name)
        if path:
            return f"{name}:{path}"
    return None


def base_args() -> list[str]:
    from clipyyy.config import get_setting
    from clipyyy.media import ffmpeg_bin

    # yt-dlp merges video and audio with ffmpeg; give it the one clipyyy found.
    args = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--no-playlist",
        "--no-warnings",
        "--ffmpeg-location",
        ffmpeg_bin(),
    ]
    runtime = js_runtime()
    if runtime:
        args += ["--js-runtimes", runtime]
    browser = get_setting("ytdlp_cookies_from_browser")
    cookies = get_setting("ytdlp_cookies_file")
    if cookies:
        args += ["--cookies", str(Path(cookies).expanduser())]
    elif browser:
        args += ["--cookies-from-browser", browser]
    return args


def _run(args: list[str]) -> subprocess.CompletedProcess:
    result = subprocess.run([*base_args(), *args], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(explain_error(result.stderr))
    return result


def explain_error(stderr: str) -> str:
    text = stderr.strip()
    errors = [line for line in text.splitlines() if line.startswith("ERROR")]
    detail = (errors[-1] if errors else text[-600:]).removeprefix("ERROR: ")
    if "Sign in to confirm" in text or "HTTP Error 429" in text:
        return (
            "YouTube is asking this network to prove it is not a bot. Wait a while and retry, or let "
            "clipyyy use your browser's YouTube login: Settings > Downloads > Use cookies from browser. "
            f"({detail})"
        )
    if "Private video" in text or "members-only" in text.lower():
        return (
            f"This video is private or members-only; add browser cookies in Settings > Downloads. ({detail})"
        )
    return f"Download failed: {detail}"


def _yt_dlp(args: list[str]) -> dict:
    return json.loads(_run(args).stdout.splitlines()[0])


def _download(url: str, output_path: Path) -> None:
    temp_path = output_path.with_suffix(".part.mp4")
    _run(["--format", VIDEO_FORMAT, "--merge-output-format", "mp4", "--output", str(temp_path), url])
    temp_path.rename(output_path)


def _link_or_copy(src: Path, dst: Path) -> None:
    try:
        dst.hardlink_to(src)
    except OSError:
        shutil.copy2(src, dst)
