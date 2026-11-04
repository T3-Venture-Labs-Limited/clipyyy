from clipyyy import db, pipeline


def test_failed_run_resumes_from_failed_stage(monkeypatch):
    calls = []
    fail = {"plan": True}

    def make(name):
        def fn(ctx):
            calls.append(name)
            if fail.get(name):
                raise RuntimeError("kaboom")
            return {"stage": name}

        return fn

    monkeypatch.setattr(
        pipeline, "STAGES", [(n, n, make(n)) for n in ("download", "transcribe", "plan", "render")]
    )
    monkeypatch.setattr(pipeline, "STAGE_NAMES", ["download", "transcribe", "plan", "render"])
    run = db.create_run("file.mp4", pipeline.ClipOptions().model_dump(), status="running")

    pipeline.execute(run)
    failed = db.get_run(run["id"])
    assert failed["status"] == "failed" and failed["error"] == "plan: kaboom"
    assert calls == ["download", "transcribe", "plan"]

    fail["plan"] = False
    pipeline.retry(run["id"])
    assert db.claim_next_run()["id"] == run["id"]
    pipeline.execute(db.get_run(run["id"]))
    assert calls[3:] == ["plan", "render"]
    assert db.get_run(run["id"])["status"] == "completed"
    assert {s["name"]: s["status"] for s in db.list_stages(run["id"])}["render"] == "done"

    pipeline.retry(run["id"], from_stage="plan")
    db.update_run(run["id"], status="running")
    pipeline.execute(db.get_run(run["id"]))
    assert calls[5:] == ["plan", "render"]


def test_options_validation():
    import pytest

    with pytest.raises(ValueError):
        pipeline.ClipOptions(min_seconds=50, max_seconds=52)
    assert pipeline.ClipOptions().aspect_ratio == "9:16"


def test_requeue_only_touches_runs_of_dead_processes():
    import os

    mine = db.create_run("a.mp4", {}, status="running")  # claimed by this (live) process
    orphan = db.create_run("b.mp4", {}, status="running")
    db.update_run(orphan["id"], claimed_by=2**22 + 12345)  # no such pid
    db.update_run(mine["id"], claimed_by=os.getppid())
    db.requeue_interrupted_runs()
    assert db.get_run(mine["id"])["status"] == "running"
    assert db.get_run(orphan["id"])["status"] == "queued"
