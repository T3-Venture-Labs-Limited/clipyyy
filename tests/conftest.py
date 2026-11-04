import pytest


@pytest.fixture(autouse=True)
def clipyyy_home(tmp_path, monkeypatch):
    """Every test gets an empty CLIPYYY_HOME and no keys from the developer's environment."""
    monkeypatch.setenv("CLIPYYY_HOME", str(tmp_path / "home"))
    for var in ("OPENROUTER_API_KEY", "PEXELS_API_KEY", "BUFFER_API_KEY", "CLIPYYY_LLM_MODEL"):
        monkeypatch.delenv(var, raising=False)
    return tmp_path / "home"


@pytest.fixture
def transcript():
    """Ten 6-second sentences, two words each per second."""
    words, sentences = [], []
    for i in range(10):
        start = i * 6.0
        sentence_words = [
            {"word": w, "start": start + j * 0.5, "end": start + j * 0.5 + 0.4}
            for j, w in enumerate(f"sentence {i} talks about building great products today.".split())
        ]
        words += sentence_words
        sentences.append(
            {
                "text": " ".join(w["word"] for w in sentence_words),
                "start": start,
                "end": sentence_words[-1]["end"],
            }
        )
    return {"language": "en", "words": words, "sentences": sentences}
