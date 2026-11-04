# Build the web UI
FROM node:22-slim AS web
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN mkdir -p ../src/clipyyy && npm run build

# Runtime: Python + ffmpeg (with libass for captions)
FROM python:3.12-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
# yt-dlp needs a JavaScript runtime to solve YouTube player challenges
COPY --from=denoland/deno:bin /deno /usr/local/bin/deno
WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src/ src/
COPY --from=web /app/src/clipyyy/web src/clipyyy/web
RUN uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH" \
    CLIPYYY_HOME=/data
VOLUME /data
EXPOSE 8000
CMD ["clipyyy", "serve", "--host", "0.0.0.0", "--port", "8000"]
