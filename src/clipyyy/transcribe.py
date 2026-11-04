"""Local transcription with word timestamps (faster-whisper)."""

from __future__ import annotations

import logging
from pathlib import Path

from clipyyy.config import home
from clipyyy.media import run_ffmpeg

logger = logging.getLogger(__name__)

SENTENCE_ENDINGS = (".", "!", "?", "…", "。", "？", "！", "؟", "।")


def transcribe(video_path: Path, work_dir: Path, model_size: str, language: str = "auto") -> dict:
    audio_path = work_dir / "audio.wav"
    run_ffmpeg(
        ["-i", str(video_path), "-vn", "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(audio_path)]
    )
    audio = load_wav(audio_path)
    lang = None if language in ("", "auto") else language
    try:
        words, detected = _run_whisper(audio, model_size, lang, "auto", "default")
    except RuntimeError as exc:
        # A GPU without the CUDA libraries faster-whisper expects: fall back to the CPU.
        if not any(k in str(exc).lower() for k in ("cuda", "cublas", "cudnn")):
            raise
        logger.warning("GPU transcription unavailable (%s); using the CPU", exc)
        words, detected = _run_whisper(audio, model_size, lang, "cpu", "int8")
    audio_path.unlink(missing_ok=True)
    return {"language": detected, "model": model_size, "words": words, "sentences": group_sentences(words)}


def _run_whisper(audio, model_size: str, language: str | None, device: str, compute_type: str):
    import warnings

    from faster_whisper import WhisperModel

    logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
    warnings.filterwarnings("ignore", message=".*unauthenticated requests to the HF Hub.*")

    model = WhisperModel(
        model_size, device=device, compute_type=compute_type, download_root=str(home() / "models" / "whisper")
    )
    segments, info = model.transcribe(
        audio, language=language, word_timestamps=True, vad_filter=True, condition_on_previous_text=False
    )
    words = [
        {"word": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3)}
        for segment in segments
        for w in segment.words or []
        if w.word.strip()
    ]
    return words, info.language


def load_wav(path: Path):
    """16 kHz mono PCM as float32. Decoding ourselves avoids PyAV version drift."""
    import wave

    import numpy as np

    with wave.open(str(path), "rb") as wav:
        frames = wav.readframes(wav.getnframes())
    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0


def group_sentences(words: list[dict], max_words: int = 60) -> list[dict]:
    """Group words into sentences on punctuation, with a cap for unpunctuated speech."""
    sentences: list[dict] = []
    current: list[dict] = []
    for word in words:
        current.append(word)
        if word["word"].endswith(SENTENCE_ENDINGS) or len(current) >= max_words:
            sentences.append(_sentence(current))
            current = []
    if current:
        sentences.append(_sentence(current))
    return sentences


def _sentence(words: list[dict]) -> dict:
    return {
        "text": " ".join(w["word"] for w in words),
        "start": words[0]["start"],
        "end": words[-1]["end"],
    }
