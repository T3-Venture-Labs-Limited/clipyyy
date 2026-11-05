# AGENTS.md

Guidance for AI coding agents working in this repository or using clipyyy as a tool.

## Using clipyyy

Use the CLI with `--json`. Start with `clipyyy doctor --json`, then `clipyyy clip <url-or-file> --json --out <dir>`. The full workflow is in [skills/clipyyy/SKILL.md](skills/clipyyy/SKILL.md). Only run `clipyyy publish` when the user explicitly asks to post to their social accounts.

## Codebase map

- `src/clipyyy/pipeline.py`: the seven stages and the runner. Each stage returns a dict that is saved to `<CLIPYYY_HOME>/runs/<id>/work/<stage>.json`; a retry skips stages whose file exists.
- `source.py`: yt-dlp downloads and local files.
- `transcribe.py`: faster-whisper with word timestamps, falling back to CPU.
- `selection.py` and `prompts/clip_selection.md`: the clip-selection prompt, JSON schema and validation (snap to sentences, enforce length, drop overlaps).
- `llm.py`: the OpenAI-compatible client. Add providers to `PROVIDERS`.
- `timeline.py`, `broll.py`, `reframe.py`, `render.py`, `captions.py`: editing, Pexels B-roll, face tracking, ffmpeg rendering and ASS captions.
- `publish.py`: Buffer GraphQL client and S3 upload.
- `db.py`: SQLite storage (runs, stages, clips, posts, settings). `config.py`: settings and paths.
- `api.py`: FastAPI routes and the built web UI. `worker.py`: the background queue worker. `cli.py`: the command line.
- `frontend/`: React + Vite + Tailwind web app. `npm run build` writes into `src/clipyyy/web`.

## Conventions

- Run `uv run pytest -q` and `uv run ruff check src tests` before finishing. Tests need ffmpeg but no network or API keys.
- Keep modules small and dependencies few. Prefer the standard library.
- Never commit API keys, cookies or files from `CLIPYYY_HOME`.

Never call `ffmpeg` or `ffprobe` by name: use `media.ffmpeg_bin()` / `media.ffprobe_bin()`. On macOS the ffmpeg that can draw captions is Homebrew's keg-only `ffmpeg-full`, which is not on the PATH.
