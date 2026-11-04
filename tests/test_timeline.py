from clipyyy.timeline import (
    MAX_WINDOW,
    MIN_WINDOW,
    assign_windows,
    build_windows,
    extract_keywords,
    plan_timeline,
)


def test_windows_cover_clip_within_limits():
    for duration in (3.0, 4.0, 9.7, 20.0, 37.3, 60.0):
        windows = build_windows(duration, [2.9, 6.1, 9.0, 15.2])
        assert windows[0][0] == 0.0
        assert abs(windows[-1][1] - duration) < 0.01
        for (s, e), nxt in zip(windows, windows[1:] + [None], strict=True):
            assert e - s <= MAX_WINDOW + 1e-6
            if len(windows) > 1:
                assert e - s >= MIN_WINDOW - 1e-6
            if nxt:
                assert nxt[0] == e


def test_broll_never_first_or_last_and_capped(transcript):
    windows = build_windows(30.0, [])
    result = assign_windows(windows, 0.0, transcript["words"], broll=True, queries=["ocean waves"])
    assert result[0]["type"] == "speaker" and result[-1]["type"] == "speaker"
    assert any(w["type"] == "broll" for w in result)
    run = 0.0
    for w in result:
        run = run + w["duration"] if w["type"] == "broll" else 0.0
        assert run <= 8.0
    assert {w["query"] for w in result if w["type"] == "broll"} == {"ocean waves"}


def test_no_broll_when_disabled(transcript):
    result = assign_windows(build_windows(30.0, []), 0.0, transcript["words"], broll=False)
    assert all(w["type"] == "speaker" for w in result)


def test_plan_timeline_uses_clip_queries(transcript):
    selection = {"clips": [{"rank": 1, "start_seconds": 0, "end_seconds": 30, "broll_queries": ["a", "b"]}]}
    plan = plan_timeline(selection, transcript, broll=True)
    queries = [w["query"] for w in plan["clips"][0]["windows"] if w["type"] == "broll"]
    assert queries[:2] == ["a", "b"]


def test_extract_keywords_skips_filler():
    assert extract_keywords("so basically we were building products") == ["building", "products"]
