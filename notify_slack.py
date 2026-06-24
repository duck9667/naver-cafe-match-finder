"""Send a message to one or more Slack recipients using a bot token.

Unlike a personal/user OAuth session, a bot token works from a non-interactive
environment like GitHub Actions. To DM a user, the bot must share a workspace
with them and have the chat:write + im:write scopes.
"""
import json
import os
import sys
import urllib.request

SLACK_API = "https://slack.com/api"


def _api_call(token, method, payload):
    req = urllib.request.Request(
        f"{SLACK_API}/{method}",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
    if not data.get("ok"):
        raise RuntimeError(f"Slack API {method} failed: {data}")
    return data


def _resolve_channel(token, recipient):
    """A Slack user ID (starts with 'U') needs a DM channel opened first.
    A channel/group ID (starts with 'C' or 'G') can be used as-is."""
    if recipient.startswith("U"):
        data = _api_call(token, "conversations.open", {"users": recipient})
        return data["channel"]["id"]
    return recipient


def notify(token, recipients, text):
    """recipients: list of Slack user IDs and/or channel IDs. Add a friend's
    user ID to this list (e.g. via the SLACK_RECIPIENTS env var) to also
    send them the same message."""
    for recipient in recipients:
        channel_id = _resolve_channel(token, recipient)
        _api_call(token, "chat.postMessage", {
            "channel": channel_id,
            "text": text,
            "mrkdwn": True,
        })


def get_recipients_from_env(var_name="SLACK_RECIPIENTS"):
    return [r.strip() for r in os.environ.get(var_name, "").split(",") if r.strip()]


if __name__ == "__main__":
    token = os.environ.get("SLACK_BOT_TOKEN")
    recipients = get_recipients_from_env()
    if not token or not recipients:
        print("[error] SLACK_BOT_TOKEN / SLACK_RECIPIENTS 환경변수가 필요합니다.", file=sys.stderr)
        sys.exit(1)
    notify(token, recipients, "Slack bot 연동 테스트 메시지입니다.")
