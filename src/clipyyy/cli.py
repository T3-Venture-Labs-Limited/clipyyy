"""Command line interface. Every command that returns data supports --json for agents."""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

from clipyyy import __version__


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    try:
        return args.func(args) or 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # surface a clean message instead of a traceback
        if args.verbose:
            raise
        _fail(str(exc), getattr(args, "json", False))
        return 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="clipyyy",
        description="Turn long videos into short vertical clips. Run `clipyyy serve` for the web UI.",
    )
    p.add_argument("--version", action="version", version=f"clipyyy {__version__}")
    p.add_argument("-v", "--verbose", action="store_true", help="show debug logs and tracebacks")
    sub = p.add_subparsers(metavar="command")

    s = sub.add_parser("serve", help="start the web UI and background worker")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--no-worker", action="store_true", help="do not process the queue")
    s.set_defaults(func=cmd_serve)

    c = sub.add_parser("clip", help="find and render clips from a URL or a local video file")
    c.add_argument("source", help="video URL (YouTube and anything yt-dlp supports) or file path")
    c.add_argument("-n", "--count", type=int, default=3, help="maximum clips (default 3)")
    c.add_argument("--min", type=float, default=20, dest="min_seconds", help="min seconds (20)")
    c.add_argument("--max", type=float, default=60, dest="max_seconds", help="max seconds (60)")
    c.add_argument("--aspect", choices=["9:16", "4:5", "1:1"], default="9:16")
    c.add_argument("--style", choices=["bold", "highlight", "minimal"], default="bold", help="caption style")
    c.add_argument("--no-captions", action="store_true")
    c.add_argument("--no-face-tracking", action="store_true", help="use a centre crop")
    c.add_argument("--broll", action="store_true", help="cut in Pexels stock footage")
    c.add_argument("--language", default="auto", help="spoken language code, e.g. en (auto)")
    c.add_argument("--instructions", default="", help="extra guidance for picking clips")
    c.add_argument("--model", help="LLM model id, e.g. google/gemini-3.8-flash")
    c.add_argument("-o", "--out", type=Path, help="copy finished clips into this folder")
    c.add_argument(
        "--queue", action="store_true", help="only queue the run for a running `clipyyy serve` worker"
    )
    c.add_argument("--json", action="store_true", help="print machine-readable JSON")
    c.set_defaults(func=cmd_clip)

    r = sub.add_parser("runs", help="list runs")
    r.add_argument("--json", action="store_true")
    r.set_defaults(func=cmd_runs)

    sh = sub.add_parser("show", help="show a run with its clips")
    sh.add_argument("run_id")
    sh.add_argument("--json", action="store_true")
    sh.set_defaults(func=cmd_show)

    rt = sub.add_parser("retry", help="resume a failed run, or redo it from a stage")
    rt.add_argument("run_id")
    rt.add_argument("--from", dest="from_stage", help="stage to redo from (e.g. select, render)")
    rt.add_argument("--json", action="store_true")
    rt.set_defaults(func=cmd_retry)

    d = sub.add_parser("delete", help="delete a run and its files")
    d.add_argument("run_id")
    d.set_defaults(func=cmd_delete)

    cfg = sub.add_parser("config", help="view or change settings (API keys, models)")
    cfg_sub = cfg.add_subparsers(metavar="action")
    cl = cfg_sub.add_parser("list", help="show all settings")
    cl.add_argument("--json", action="store_true")
    cl.set_defaults(func=cmd_config_list)
    cs = cfg_sub.add_parser("set", help="save a setting")
    cs.add_argument("key")
    cs.add_argument("value")
    cs.set_defaults(func=cmd_config_set)
    cu = cfg_sub.add_parser("unset", help="clear a saved setting")
    cu.add_argument("key")
    cu.set_defaults(func=cmd_config_unset)
    cfg.set_defaults(func=cmd_config_list, json=False)

    doc = sub.add_parser("doctor", help="check ffmpeg, keys and optional integrations")
    doc.add_argument("--json", action="store_true")
    doc.set_defaults(func=cmd_doctor)

    m = sub.add_parser("models", help="list models that support structured output")
    m.add_argument("search", nargs="?", default="")
    m.add_argument("--json", action="store_true")
    m.set_defaults(func=cmd_models)

    ch = sub.add_parser("channels", help="list your Buffer channels")
    ch.add_argument("--json", action="store_true")
    ch.set_defaults(func=cmd_channels)

    pb = sub.add_parser("publish", help="send a clip to Buffer")
    pb.add_argument("clip_id")
    pb.add_argument(
        "--channel", action="append", required=True, dest="channels", help="Buffer channel id (repeatable)"
    )
    pb.add_argument("--mode", choices=["queue", "now", "schedule", "draft"], default="queue")
    pb.add_argument("--at", help="ISO time for --mode schedule, e.g. 2026-11-05T18:00:00Z")
    pb.add_argument("--json", action="store_true")
    pb.set_defaults(func=cmd_publish)
    return p


# ── commands ─────────────────────────────────────────────────────────────────


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from clipyyy.api import WEB_DIR, create_app

    if not (WEB_DIR / "index.html").exists():
        print(
            "Note: the web UI is not built; only the API is available. "
            "Run `npm --prefix frontend run build` from the repo.",
            file=sys.stderr,
        )
    print(f"clipyyy {__version__} running at http://{args.host}:{args.port}", file=sys.stderr)
    logging.getLogger().setLevel(logging.INFO)
    uvicorn.run(
        create_app(start_worker=not args.no_worker), host=args.host, port=args.port, log_level="warning"
    )
    return 0


def cmd_clip(args: argparse.Namespace) -> int:
    from clipyyy import db, pipeline
    from clipyyy.source import is_url

    source = args.source if is_url(args.source) else str(Path(args.source).expanduser().resolve())
    options = pipeline.ClipOptions(
        clip_count=args.count,
        min_seconds=args.min_seconds,
        max_seconds=args.max_seconds,
        aspect_ratio=args.aspect,
        caption_style=args.style,
        captions=not args.no_captions,
        face_tracking=not args.no_face_tracking,
        broll=args.broll,
        language=args.language,
        instructions=args.instructions,
        model=args.model,
    ).model_dump()

    if args.queue:
        run = db.create_run(source, options)
        _emit(args, {"run_id": run["id"], "status": "queued"}, f"Queued run {run['id']}")
        return 0

    run = db.create_run(source, options, status="running")
    _log(args, f"Run {run['id']}")
    pipeline.execute(run, on_stage=lambda name: _log(args, f"  {name}…"))
    return _report(args, run["id"])


def cmd_retry(args: argparse.Namespace) -> int:
    from clipyyy import db, pipeline

    run = _require_run(args.run_id)
    if run["status"] == "running":
        raise RuntimeError("That run is still running")
    pipeline.retry(run["id"], args.from_stage)
    db.update_run(run["id"], status="running", claimed_by=os.getpid())
    pipeline.execute(db.get_run(run["id"]), on_stage=lambda name: _log(args, f"  {name}…"))
    return _report(args, run["id"])


def _report(args: argparse.Namespace, run_id: str) -> int:
    from clipyyy.api import run_detail

    detail = run_detail(run_id)
    clips = detail["clips"]
    out_files: dict[str, str] = {}
    if getattr(args, "out", None) and clips:
        args.out.mkdir(parents=True, exist_ok=True)
        for clip in clips:
            if clip["status"] == "ready":
                src = _clip_path(clip["id"])
                dest = args.out / src.name
                shutil.copy2(src, dest)
                out_files[clip["id"]] = str(dest.resolve())
    payload = {
        "run_id": run_id,
        "status": detail["status"],
        "title": detail["title"],
        "error": detail["error"],
        "clips": [
            {
                "id": c["id"],
                "rank": c["rank"],
                "status": c["status"],
                "title": c["title"],
                "post_title": c["post_title"],
                "caption": c["caption"],
                "hashtags": c["hashtags"],
                "start_seconds": c["start_seconds"],
                "end_seconds": c["end_seconds"],
                "duration_seconds": c["duration_seconds"],
                "score": c["score"],
                "file": out_files.get(c["id"]) or (str(_clip_path(c["id"])) if c["filename"] else None),
                "error": c["error"],
            }
            for c in clips
        ],
    }
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"{detail['title'] or run_id} · {detail['status']}")
        if detail["error"]:
            print(f"Error: {detail['error']}")
        for c in payload["clips"]:
            print(f"\n#{c['rank']} {c['title']} ({c['duration_seconds'] or '?'}s) [{c['status']}]")
            if c["file"]:
                print(f"   file: {c['file']}")
            print(f"   {c['caption']} {' '.join(c['hashtags'] or [])}")
    return 0 if detail["status"] == "completed" else 1


def cmd_runs(args: argparse.Namespace) -> int:
    from clipyyy import db

    runs = db.list_runs()
    if args.json:
        print(json.dumps(runs, indent=2, ensure_ascii=False))
        return 0
    for run in runs:
        print(
            f"{run['id']}  {run['status']:<10} {run['clip_count']} clips  "
            f"{run['created_at'][:16]}  {run['title'] or run['source']}"
        )
    if not runs:
        print("No runs yet. Try: clipyyy clip <youtube-url>")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    _require_run(args.run_id)
    args.out = None
    return _report(args, args.run_id)


def cmd_delete(args: argparse.Namespace) -> int:
    from clipyyy import pipeline

    run = _require_run(args.run_id)
    if run["status"] == "running":
        raise RuntimeError("That run is still running")
    pipeline.delete(run["id"])
    print(f"Deleted {run['id']}")
    return 0


def cmd_config_list(args: argparse.Namespace) -> int:
    from clipyyy import db
    from clipyyy.config import SETTINGS, get_setting, mask

    rows = []
    for key, spec in SETTINGS.items():
        value = get_setting(key)
        rows.append(
            {
                "key": key,
                "value": mask(value) if spec.secret else value,
                "saved": db.get_setting(key) is not None,
                "env": spec.env,
                "description": spec.description,
            }
        )
    if getattr(args, "json", False):
        print(json.dumps(rows, indent=2))
    else:
        for row in rows:
            print(f"{row['key']:<24} {row['value'] or '-':<32} {row['description']}")
    return 0


def cmd_config_set(args: argparse.Namespace) -> int:
    from clipyyy import db
    from clipyyy.config import SETTINGS

    if args.key not in SETTINGS:
        raise RuntimeError(f"Unknown setting '{args.key}'. Run `clipyyy config list`.")
    db.set_setting(args.key, args.value)
    print(f"Saved {args.key}")
    return 0


def cmd_config_unset(args: argparse.Namespace) -> int:
    from clipyyy import db
    from clipyyy.config import SETTINGS

    if args.key not in SETTINGS:
        raise RuntimeError(f"Unknown setting '{args.key}'")
    db.set_setting(args.key, None)
    print(f"Cleared {args.key}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    from clipyyy.doctor import checks

    results = checks()
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for c in results:
            mark = "ok " if c["ok"] else ("ERR" if c["required"] else " - ")
            print(f"[{mark}] {c['name']:<9} {c['detail']}")
    return 0 if all(c["ok"] for c in results if c["required"]) else 1


def cmd_models(args: argparse.Namespace) -> int:
    from clipyyy.llm import list_models

    models = [m for m in list_models() if args.search.lower() in m["id"].lower()]
    if args.json:
        print(json.dumps(models, indent=2))
    else:
        for m in models:
            price = m["prompt_price_per_million"]
            print(
                f"{m['id']:<50} {m['context_length'] or '?':>8} ctx  "
                f"${price if price is not None else '?'}/M in"
            )
    return 0


def cmd_channels(args: argparse.Namespace) -> int:
    from clipyyy.publish import BufferClient

    channels = BufferClient().channels()
    if args.json:
        print(json.dumps(channels, indent=2))
    else:
        for ch in channels:
            print(f"{ch['id']}  {ch['service']:<10} {ch['name']}")
    return 0


def cmd_publish(args: argparse.Namespace) -> int:
    from clipyyy.publish import publish_clip

    at = datetime.fromisoformat(args.at.replace("Z", "+00:00")) if args.at else None
    posts = publish_clip(args.clip_id, args.channels, args.mode, at)
    if args.json:
        print(json.dumps(posts, indent=2))
    else:
        for post in posts:
            print(
                f"{post['channel_name'] or post['channel_id']}: {post['status']}"
                + (f" ({post['error']})" if post.get("error") else "")
            )
    return 0 if all(p["status"] != "failed" for p in posts) else 1


# ── helpers ──────────────────────────────────────────────────────────────────


def _require_run(run_id: str) -> dict:
    from clipyyy import db

    run = db.get_run(run_id)
    if run is None:
        raise RuntimeError(f"No run with id {run_id}")
    return run


def _clip_path(clip_id: str) -> Path:
    from clipyyy import db

    return Path(db.get_clip(clip_id)["file_path"])


def _log(args: argparse.Namespace, message: str) -> None:
    print(message, file=sys.stderr)


def _emit(args: argparse.Namespace, payload: dict, text: str) -> None:
    print(json.dumps(payload) if args.json else text)


def _fail(message: str, as_json: bool) -> None:
    if as_json:
        print(json.dumps({"error": message}))
    else:
        print(f"Error: {message}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
