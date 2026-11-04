"""HTTP API and web UI."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import zipfile
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from clipyyy import __version__, db, pipeline
from clipyyy.config import PACKAGE_DIR, SETTINGS, get_setting, mask, uploads_dir
from clipyyy.doctor import checks
from clipyyy.publish import BufferClient, PublishError, PublishMode, publish_clip
from clipyyy.worker import Worker

WEB_DIR = PACKAGE_DIR / "web"


class CreateRuns(BaseModel):
    sources: list[str] = Field(..., min_length=1, max_length=50)
    options: pipeline.ClipOptions = pipeline.ClipOptions()


class RetryRun(BaseModel):
    from_stage: str | None = None


class UpdateSettings(BaseModel):
    values: dict[str, str | None]


class PublishRequest(BaseModel):
    channel_ids: list[str] = Field(..., min_length=1)
    mode: PublishMode = "queue"
    scheduled_at: datetime | None = None
    text: str | None = None
    title: str | None = None


def create_app(start_worker: bool = True) -> FastAPI:
    worker = Worker() if start_worker else None

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if worker:
            worker.start()
        yield
        if worker:
            worker.stop()

    app = FastAPI(title="clipyyy", version=__version__, lifespan=lifespan)

    # ── health & settings ────────────────────────────────────────────────────

    @app.get("/api/health")
    def health() -> dict:
        return {
            "version": __version__,
            "checks": checks(),
            "queue": db.queue_counts(),
            "worker": bool(worker),
        }

    @app.get("/api/settings")
    def get_settings() -> list[dict]:
        result = []
        for key, spec in SETTINGS.items():
            stored = db.get_setting(key)
            value = get_setting(key)
            source = "app" if stored else "env" if os.environ.get(spec.env) else "default"
            result.append(
                {
                    "key": key,
                    "value": mask(value) if spec.secret else value,
                    "is_set": bool(value),
                    "secret": spec.secret,
                    "source": source,
                    "env": spec.env,
                    "description": spec.description,
                }
            )
        return result

    @app.put("/api/settings")
    def put_settings(body: UpdateSettings) -> list[dict]:
        for key, value in body.values.items():
            if key not in SETTINGS:
                raise HTTPException(400, f"Unknown setting: {key}")
            if SETTINGS[key].secret and value and "••••" in value:
                continue  # unchanged masked value sent back by the UI
            db.set_setting(key, value.strip() if value else None)
        return get_settings()

    @app.get("/api/models")
    def models() -> list[dict]:
        from clipyyy.llm import list_models

        try:
            return list_models()
        except Exception as exc:
            raise HTTPException(502, f"Could not load models: {exc}") from exc

    # ── runs ─────────────────────────────────────────────────────────────────

    @app.post("/api/uploads")
    def upload(file: UploadFile) -> dict:
        name = Path(file.filename or "upload.mp4").name
        target = uploads_dir() / f"{db.new_id()}-{name}"
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as fh:
            shutil.copyfileobj(file.file, fh, length=1024 * 1024)
        return {"source": str(target), "name": name}

    @app.post("/api/runs")
    def create_runs(body: CreateRuns) -> list[dict]:
        runs = [
            db.create_run(source.strip(), body.options.model_dump())
            for source in body.sources
            if source.strip()
        ]
        if worker:
            worker.wake()
        return runs

    @app.get("/api/runs")
    def list_runs() -> list[dict]:
        return db.list_runs()

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> dict:
        return run_detail(run_id)

    @app.post("/api/runs/{run_id}/retry")
    def retry_run(run_id: str, body: RetryRun | None = None) -> dict:
        run = _run_or_404(run_id)
        if run["status"] in {"queued", "running"}:
            raise HTTPException(409, "Run is already queued or running")
        from_stage = body.from_stage if body else None
        if from_stage and from_stage not in pipeline.STAGE_NAMES:
            raise HTTPException(400, f"Unknown stage: {from_stage}")
        pipeline.retry(run_id, from_stage)
        if worker:
            worker.wake()
        return run_detail(run_id)

    @app.delete("/api/runs/{run_id}")
    def delete_run(run_id: str) -> dict:
        run = _run_or_404(run_id)
        if run["status"] == "running":
            raise HTTPException(409, "Wait for the run to finish before deleting it")
        pipeline.delete(run_id)
        return {"deleted": run_id}

    @app.get("/api/runs/{run_id}/download")
    def download_run(run_id: str) -> FileResponse:
        run = _run_or_404(run_id)
        clips = [c for c in db.list_clips(run_id) if c["status"] == "ready" and c["file_path"]]
        if not clips:
            raise HTTPException(404, "No clips to download yet")
        fd, tmp = tempfile.mkstemp(suffix=".zip")
        os.close(fd)
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_STORED) as zf:
            for clip in clips:
                zf.write(clip["file_path"], Path(clip["file_path"]).name)
            zf.writestr(
                "clips.json", json.dumps([_clip_public(c) for c in clips], indent=2, ensure_ascii=False)
            )
        name = f"clipyyy-{_safe(run['title'] or run_id)}.zip"
        return FileResponse(
            tmp, filename=name, media_type="application/zip", background=BackgroundTask(os.unlink, tmp)
        )

    # ── clips & publishing ───────────────────────────────────────────────────

    @app.get("/api/clips/{clip_id}/video")
    def clip_video(clip_id: str, download: bool = False) -> FileResponse:
        clip = db.get_clip(clip_id)
        if not clip or not clip["file_path"] or not Path(clip["file_path"]).exists():
            raise HTTPException(404, "Clip file not found")
        path = Path(clip["file_path"])
        return FileResponse(
            path,
            media_type="video/mp4",
            filename=path.name if download else None,
            content_disposition_type="attachment" if download else "inline",
        )

    @app.get("/api/clips/{clip_id}/poster")
    def clip_poster(clip_id: str) -> FileResponse:
        from clipyyy.render import make_poster, poster_path

        clip = db.get_clip(clip_id)
        if not clip or not clip["file_path"] or not Path(clip["file_path"]).exists():
            raise HTTPException(404, "Clip file not found")
        poster = poster_path(Path(clip["file_path"]))
        if not poster.exists():
            make_poster(Path(clip["file_path"]), 1.0)
        return FileResponse(poster, media_type="image/jpeg")

    @app.get("/api/buffer/channels")
    def buffer_channels() -> list[dict]:
        try:
            return BufferClient().channels()
        except PublishError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.get("/api/buffer/organizations")
    def buffer_organizations() -> list[dict]:
        try:
            return BufferClient().organizations()
        except PublishError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/clips/{clip_id}/publish")
    def publish(clip_id: str, body: PublishRequest) -> list[dict]:
        try:
            return publish_clip(
                clip_id, body.channel_ids, body.mode, body.scheduled_at, body.text, body.title
            )
        except PublishError as exc:
            raise HTTPException(400, str(exc)) from exc

    # ── web UI ───────────────────────────────────────────────────────────────

    if (WEB_DIR / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=WEB_DIR / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            if path.startswith("api/"):
                raise HTTPException(404)
            candidate = (WEB_DIR / path).resolve()
            if path and candidate.is_file() and WEB_DIR.resolve() in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(WEB_DIR / "index.html")

    return app


def run_detail(run_id: str) -> dict:
    run = _run_or_404(run_id)
    stage_rows = {s["name"]: s for s in db.list_stages(run_id)}
    stages = [
        {
            "name": name,
            "label": label,
            **{
                k: v
                for k, v in stage_rows.get(name, {}).items()
                if k in {"status", "error", "started_at", "finished_at"}
            },
        }
        for name, label, _ in pipeline.STAGES
    ]
    for stage in stages:
        stage.setdefault("status", "pending")
    source_file = pipeline.run_dir(run_id) / "work" / "download.json"
    source_duration = None
    if source_file.exists():
        source_duration = json.loads(source_file.read_text(encoding="utf-8")).get("duration_seconds")
    return {
        **run,
        "source_duration": source_duration,
        "stages": stages,
        "clips": [_clip_public(c) for c in db.list_clips(run_id)],
        "posts": db.list_posts(run_id=run_id),
    }


def _clip_public(clip: dict) -> dict:
    data = {k: v for k, v in clip.items() if k != "file_path"}
    data["filename"] = Path(clip["file_path"]).name if clip.get("file_path") else None
    data["video_url"] = f"/api/clips/{clip['id']}/video"
    data["poster_url"] = f"/api/clips/{clip['id']}/poster"
    data["download_url"] = f"/api/clips/{clip['id']}/video?download=true"
    return data


def _run_or_404(run_id: str) -> dict[str, Any]:
    run = db.get_run(run_id)
    if run is None:
        raise HTTPException(404, "Run not found")
    return run


def _safe(text: str) -> str:
    from clipyyy.render import slugify

    return slugify(text)
