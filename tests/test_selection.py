import pytest

from clipyyy.llm import LLMError
from clipyyy.selection import build_prompt, clean_caption, clean_hashtags, select_clips, snap, validate_clips

OPTIONS = {"clip_count": 3, "min_seconds": 15, "max_seconds": 30, "instructions": ""}


def raw(start, end, rank=1, **extra):
    return {
        "rank": rank,
        "start_seconds": start,
        "end_seconds": end,
        "title": f"t{rank}",
        "post_title": "p",
        "caption": "c",
        "hashtags": ["a"],
        "rationale": "r",
        "overall_score": 8,
        **extra,
    }


def test_snap_moves_to_sentence_boundaries(transcript):
    start, end = snap(6.3, 23.0, transcript["sentences"], 15, 30)
    assert start == 6.0
    assert end == pytest.approx(transcript["sentences"][3]["end"])


def test_snap_extends_short_clip_to_minimum(transcript):
    start, end = snap(0.1, 5.0, transcript["sentences"], 15, 30)
    assert end - start >= 15


def test_snap_trims_long_clip_at_sentence_end(transcript):
    start, end = snap(0.0, 59.0, transcript["sentences"], 15, 30)
    assert end - start <= 30
    assert end in {s["end"] for s in transcript["sentences"]}


def test_validate_drops_overlaps_and_renumbers(transcript):
    clips = validate_clips([raw(0, 20, 1), raw(5, 25, 2), raw(36, 55, 3)], transcript, OPTIONS)
    assert [c["rank"] for c in clips] == [1, 2]
    assert clips[1]["start_seconds"] == 36.0
    assert clips[0]["transcript"].startswith("sentence 0")


def test_validate_respects_clip_count(transcript):
    options = {**OPTIONS, "clip_count": 1}
    assert len(validate_clips([raw(0, 20, 1), raw(36, 55, 2)], transcript, options)) == 1


def test_validate_skips_garbage(transcript):
    assert validate_clips([{"rank": 1, "start_seconds": "x"}], transcript, OPTIONS) == []


def test_caption_and_hashtag_cleanup():
    assert clean_caption("Great point (87 chars)") == "Great point"
    tags, caption = clean_hashtags(["growth", "#Startups", "#growth"], "Build things #founders #Startups")
    assert caption == "Build things"
    assert tags == ["#growth", "#Startups", "#founders"]


def test_prompt_includes_options_and_instructions(transcript):
    system, user = build_prompt(
        {"title": "Talk", "uploader": "Ann", "duration_seconds": 60},
        transcript,
        {**OPTIONS, "instructions": "End captions with 'Follow for more'"},
    )
    assert "up to 3" in system and "between 15 and 30 seconds" in system
    assert "Follow for more" in system
    assert "[0.0-" in user and "Talk by Ann" in user


class FakeLLM:
    model = "fake"

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def complete_json(self, system, user, schema, name):
        self.calls += 1
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_select_clips_retries_until_valid(transcript):
    llm = FakeLLM([LLMError("boom"), {"clips": [{"rank": 1}]}, {"clips": [raw(0, 20)]}])
    result = select_clips(llm, {"title": "x"}, transcript, OPTIONS)
    assert llm.calls == 3
    assert result["model"] == "fake" and len(result["clips"]) == 1


def test_select_clips_without_speech_fails():
    with pytest.raises(ValueError, match="No speech"):
        select_clips(FakeLLM([]), {}, {"sentences": []}, OPTIONS)
