# naver-cafe-match-finder

네이버 카페 게시글 검색 API로 특정 카페의 매칭/모집글을 주기적으로 찾아서 Slack DM으로 알려주는 도구.

기본값은 "모두의 풋살축구" 카페에서 용산/도곡 지역 풋살 매칭글을 찾는 용도로 맞춰져 있지만, 환경변수로 카페명/검색어/제외 키워드를 바꿔서 다른 카페·다른 주제에도 그대로 쓸 수 있다.

## 한계 (먼저 알아야 할 것)

네이버 카페 게시글 검색 API(`/v1/search/cafearticle.json`)는 **특정 카페를 지정해서 검색하는 기능이 없다.** 전체 카페글 검색 결과에서 응답에 포함된 `cafename` 필드로 내가 원하는 카페인지를 사후에 걸러내는 방식만 가능하다. 즉:

- 그 카페가 네이버 검색에 색인해둔 글만 잡힌다 (비공개 카페거나 색인이 안 된 최신 글은 누락될 수 있음)
- 게시글 본문 전체는 못 가져온다. API가 주는 `description`은 본문 앞부분을 잘라낸 짧은 발췌문뿐이다

## 준비물

1. [네이버 개발자센터](https://developers.naver.com/apps/#/register)에서 애플리케이션 등록 → "검색" API 사용 설정 → Client ID/Secret 발급
2. Python 3
3. (선택) Slack에 알림을 보내고 싶다면 Slack 워크스페이스 접근 권한 / MCP 연동

## 설치

```bash
git clone <이 레포 URL>
cd naver-cafe-match-finder
cp .env.example .env
```

`.env` 파일을 열어 발급받은 키를 채운다:

```
NAVER_CLIENT_ID=발급받은_client_id
NAVER_CLIENT_SECRET=발급받은_client_secret
```

다른 카페/검색어를 쓰려면 `.env`에 아래도 같이 채운다 (생략하면 풋살 기본값 사용):

```
TARGET_CAFE=대상 카페 이름 (cafename 필드와 정확히 일치해야 함)
SEARCH_QUERIES=검색어1,검색어2,검색어3
EXCLUDE_KEYWORDS=제목에서 제외할 키워드1,키워드2
REMOVE_FROM_TITLE=제목에서 지울 단어1,단어2
```

## 실행

```bash
set -a; source .env; set +a
python3 search_futsal.py
```

- 검색 결과 중 `TARGET_CAFE`와 일치하고, `EXCLUDE_KEYWORDS`가 제목에 없는 글만 골라서 출력한다.
- 한 번 출력된 글의 링크는 `seen_links.json`에 저장되어, 이후 실행에서는 "새 글"만 출력한다 (최초 1회는 검색되는 모든 글이 새 글로 잡힌다는 점 주의).
- 더 이상 추적하지 않고 다시 전체를 새 글로 보고 싶으면 `seen_links.json`을 삭제하면 된다.

## 자동 실행 (Claude Code 사용 시)

Claude Code의 scheduled task 기능으로 주기적 실행 + Slack DM 알림까지 자동화할 수 있다. 직접 만들 때 참고할 포인트:

- 일정 주기(예: 3시간마다)로 `search_futsal.py`를 실행
- 출력된 제목 + description을 LLM이 직접 읽고, 날짜/시간/장소/인원수를 정리된 형식으로 재구성 (날짜 표기가 "26.6.28", "6월19일", "26년 6월 21일" 등 제각각이라 정규식보다 LLM이 해석하는 게 안정적)
- description까지 읽고 "용병 모집/팀원 모집/구장 양도" 등 실제로는 매칭글이 아닌 경우 한 번 더 걸러내기
- 매치 날짜가 실행일 기준 과거면 제외 (기간 필터)
- 결과를 Slack DM(MCP `slack_send_message`)으로 전송. Slack 도구에 표준 마크다운(`**bold**`)으로 입력하면 Slack 문법(`*bold*`)으로 자동 변환되니, 굳이 Slack 문법을 직접 쓰지 않아도 된다 (단, `*텍스트*`처럼 별표 1개로 직접 쓰면 이탤릭으로 변환되어버리니 주의)

## 파일 구성

- `search_futsal.py` — 검색 + 필터링 + 신규글 추적 스크립트
- `.env.example` — 환경변수 템플릿 (`.env`는 git에 올리지 않음)
- `seen_links.json` — 이미 알려준 글의 링크 기록 (git에 올리지 않음, 최초 실행 시 자동 생성)
