#!/usr/bin/env python3
import json
import os
import re
import sys
import urllib.parse
import urllib.request

CLIENT_ID = os.environ.get("NAVER_CLIENT_ID")
CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET")

TARGET_CAFE = os.environ.get("TARGET_CAFE", "모두의 풋살축구")
QUERIES = [
    q.strip()
    for q in os.environ.get("SEARCH_QUERIES", "용산 풋살,도곡 풋살,용산 풋살 매칭,도곡 풋살 매칭").split(",")
    if q.strip()
]
EXCLUDE_KEYWORDS = [
    kw.strip()
    for kw in os.environ.get(
        "EXCLUDE_KEYWORDS", "초청,매칭완료,매치완료,마감,용병,회원 모집,팀원 구합니다,양도"
    ).split(",")
    if kw.strip()
]
REMOVE_FROM_TITLE = [
    w.strip()
    for w in os.environ.get("REMOVE_FROM_TITLE", "스타디움").split(",")
    if w.strip()
]
STATE_FILE = os.path.join(os.path.dirname(__file__), "seen_links.json")

API_URL = "https://openapi.naver.com/v1/search/cafearticle.json"


def search(query, display=20):
    url = f"{API_URL}?{urllib.parse.urlencode({'query': query, 'display': display, 'sort': 'date'})}"
    req = urllib.request.Request(url)
    req.add_header("X-Naver-Client-Id", CLIENT_ID)
    req.add_header("X-Naver-Client-Secret", CLIENT_SECRET)
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def load_seen():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_seen(seen):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, ensure_ascii=False, indent=2)


def strip_tags(text):
    return re.sub(r"<.*?>", "", text)


def get_new_items():
    """Search all configured queries, filter to the target cafe, drop
    already-seen links and excluded titles, and persist newly-seen links.
    Returns a list of {title, link, description, query} dicts."""
    if not CLIENT_ID or not CLIENT_SECRET:
        raise RuntimeError(
            "NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 환경변수가 설정되지 않았습니다."
        )

    seen = load_seen()
    new_items = []

    for query in QUERIES:
        try:
            data = search(query)
        except Exception as e:
            print(f"[error] query={query!r}: {e}", file=sys.stderr)
            continue

        for item in data.get("items", []):
            if item.get("cafename") != TARGET_CAFE:
                continue
            title = strip_tags(item.get("title", ""))
            for word in REMOVE_FROM_TITLE:
                title = title.replace(word, "")
            if any(kw in title for kw in EXCLUDE_KEYWORDS):
                continue
            link = item.get("link")
            if link in seen:
                continue
            seen.add(link)
            new_items.append({
                "title": title,
                "link": link,
                "description": strip_tags(item.get("description", "")),
                "query": query,
            })

    save_seen(seen)
    return new_items


def main():
    try:
        new_items = get_new_items()
    except RuntimeError as e:
        print(f"[error] {e}", file=sys.stderr)
        sys.exit(1)

    if not new_items:
        print("새로운 게시글 없음")
        return

    for item in new_items:
        print(f"[{item['query']}] {item['title']}\n링크: {item['link']}\n{item['description']}\n")


if __name__ == "__main__":
    main()
