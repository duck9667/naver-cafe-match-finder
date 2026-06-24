#!/usr/bin/env python3
"""Entry point for scheduled runs (e.g. GitHub Actions cron).

1. Search the target cafe for new matching posts (search_futsal.get_new_items).
2. Parse each post's date/time/location/team size with parse_match.format_entry,
   dropping posts whose match date is already in the past.
3. If anything survives, send one Slack message (bold header + bullet list)
   to every recipient in SLACK_RECIPIENTS. If nothing new/relevant was
   found, send nothing — already-notified posts are never re-sent.
"""
import os
import sys
from datetime import timezone, timedelta

import notify_slack
import parse_match
import search_futsal

CAFE_LABEL = search_futsal.TARGET_CAFE
KST = timezone(timedelta(hours=9))


def main():
    from datetime import datetime
    today = datetime.now(KST).date()

    token = os.environ.get("SLACK_BOT_TOKEN")
    recipients = notify_slack.get_recipients_from_env()
    if not token or not recipients:
        print("[error] SLACK_BOT_TOKEN / SLACK_RECIPIENTS 환경변수가 필요합니다.", file=sys.stderr)
        sys.exit(1)

    try:
        raw_items = search_futsal.get_new_items()
    except RuntimeError as e:
        notify_slack.notify(token, recipients, f"[{CAFE_LABEL} 검색 오류] {e}")
        sys.exit(1)

    lines = []
    for item in raw_items:
        try:
            line = parse_match.format_entry(item, today)
        except Exception as e:
            print(f"[warn] failed to parse {item['link']}: {e}", file=sys.stderr)
            continue
        if line:
            lines.append(line)

    if not lines:
        print("새로운 매칭 글 없음 (또는 전부 필터링됨) - Slack 메시지 보내지 않음")
        return

    header = f"**{CAFE_LABEL} - 매칭 새 글 ({len(lines)}건)**"
    message = header + "\n" + "\n".join(f"• {line}" for line in lines)
    notify_slack.notify(token, recipients, message)


if __name__ == "__main__":
    main()
