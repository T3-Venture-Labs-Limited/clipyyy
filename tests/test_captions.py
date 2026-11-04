from clipyyy.captions import STYLES, _ass_color, _ts, chunk_words, clip_words, emphasis_index, write_ass


def test_clip_words_are_rebased(transcript):
    words = clip_words(transcript, 6.0, 10.0)
    assert words[0]["start"] == 0.0
    assert all(w["end"] <= 4.0 for w in words)


def test_chunks_respect_limits(transcript):
    style = STYLES["bold"]
    for chunk in chunk_words(transcript["words"], style):
        assert len(chunk) <= style.max_words
        assert len(" ".join(w["word"] for w in chunk)) <= style.max_chars or len(chunk) == 1


def test_emphasis_picks_long_content_word():
    chunk = [{"word": w} for w in ["we", "built", "everything"]]
    assert emphasis_index(chunk) == 2
    assert emphasis_index([{"word": "it"}, {"word": "was"}]) is None


def test_write_ass_has_one_event_per_word(tmp_path, transcript):
    words = clip_words(transcript, 0, 12)
    path = write_ass(words, tmp_path / "c.ass", 1080, 1920, "bold")
    text = path.read_text()
    assert "PlayResX: 1080" in text and "Archivo Black" in text
    events = [line for line in text.splitlines() if line.startswith("Dialogue:")]
    assert 0 < len(events) <= len(words)
    assert "\\fad(120,0)" in events[0]


def test_ass_helpers():
    assert _ass_color("FFD400") == "&H0000D4FF&"
    assert _ts(3661.257) == "1:01:01.26"
