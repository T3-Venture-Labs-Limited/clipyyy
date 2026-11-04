from clipyyy import db
from clipyyy.source import base_args, explain_error


def test_bot_check_gets_actionable_message():
    stderr = "WARNING: x\nERROR: [youtube] abc: Sign in to confirm you're not a bot. Use --cookies"
    message = explain_error(stderr)
    assert "Settings > Downloads" in message and "not a bot" in message


def test_other_errors_keep_the_yt_dlp_line():
    assert explain_error("ERROR: Unsupported URL: https://x") == "Download failed: Unsupported URL: https://x"


def test_cookie_settings_are_passed_to_yt_dlp(tmp_path):
    assert "--cookies-from-browser" not in base_args()
    db.set_setting("ytdlp_cookies_from_browser", "firefox")
    args = base_args()
    assert args[args.index("--cookies-from-browser") + 1] == "firefox"
    db.set_setting("ytdlp_cookies_file", str(tmp_path / "c.txt"))
    args = base_args()
    assert "--cookies" in args and "--cookies-from-browser" not in args
