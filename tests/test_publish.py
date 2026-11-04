import json

import httpx
import pytest

from clipyyy import db
from clipyyy.publish import BufferClient, PublishError, platform_metadata, publish_clip


def buffer_transport(log):
    def handler(request):
        body = json.loads(request.content)
        log.append(body)
        q = body["query"]
        if "organizations" in q:
            return httpx.Response(
                200, json={"data": {"account": {"organizations": [{"id": "org1", "name": "Me"}]}}}
            )
        if "channels" in q:
            return httpx.Response(
                200,
                json={
                    "data": {
                        "channels": [
                            {"id": "yt1", "name": "My YouTube", "service": "youtube", "avatar": ""},
                            {"id": "tt1", "name": "My TikTok", "service": "tiktok", "avatar": ""},
                        ]
                    }
                },
            )
        if body["variables"]["input"]["channelId"] == "tt1":
            return httpx.Response(
                200, json={"data": {"createPost": {"__typename": "MutationError", "message": "nope"}}}
            )
        return httpx.Response(
            200,
            json={
                "data": {
                    "createPost": {
                        "__typename": "PostActionSuccess",
                        "post": {"id": "p1", "status": "buffer"},
                    }
                }
            },
        )

    return httpx.MockTransport(handler)


def make_clip(tmp_path):
    run = db.create_run("https://example.com/v", {})
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake")
    clip = db.replace_clips(
        run["id"],
        [
            {
                "rank": 1,
                "start_seconds": 0,
                "end_seconds": 30,
                "title": "T",
                "post_title": "Post title",
                "caption": "Caption",
                "hashtags": ["#a", "#b"],
                "rationale": "",
                "score": 8,
                "transcript": "",
                "file_path": str(video),
                "status": "ready",
            }
        ],
    )[0]
    return clip


def test_publish_records_each_channel(tmp_path):
    log = []
    clip = make_clip(tmp_path)
    client = BufferClient("token", transport=buffer_transport(log))
    posts = publish_clip(
        clip["id"],
        ["yt1", "tt1"],
        "queue",
        client=client,
        uploader=lambda path, key: f"https://cdn.example.com/{key}",
    )
    assert [p["status"] for p in posts] == ["sent_to_buffer", "failed"]
    assert posts[1]["error"] == "nope"
    create = next(b for b in log if "createPost" in b["query"])["variables"]["input"]
    assert create["assets"] == [{"video": {"url": posts[0]["media_url"]}}]
    assert create["mode"] == "addToQueue"
    assert create["text"] == "Caption\n\n#a #b"
    assert create["metadata"]["youtube"]["title"] == "Post title"
    assert len(db.list_posts(clip_id=clip["id"])) == 2


def test_publish_rejects_unknown_channel(tmp_path):
    clip = make_clip(tmp_path)
    client = BufferClient("token", transport=buffer_transport([]))
    with pytest.raises(PublishError, match="Unknown"):
        publish_clip(clip["id"], ["nope"], client=client, uploader=lambda p, k: "https://x")


def test_buffer_requires_key():
    with pytest.raises(PublishError, match="Buffer API key"):
        BufferClient()


def test_platform_metadata():
    assert platform_metadata("instagram", "x") == {"instagram": {"type": "reel", "shouldShareToFeed": True}}
    assert platform_metadata("tiktok", "x") is None
