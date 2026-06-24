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

Claude Code의 scheduled task 기능으로 주기적 실행 + Slack DM 알림까지 자동화할 수 있다. 실제로 사용한 지침 전문은 [AUTOMATION.md](./AUTOMATION.md)에 그대로 정리해뒀다 — 그대로 복사해서 본인 환경(경로, Slack 채널/유저 ID, 카페명)에 맞게 값만 바꾸면 재현 가능하다. 핵심 포인트:

- 일정 주기(예: 3시간마다)로 `search_futsal.py`를 실행
- 출력된 제목 + description을 LLM이 직접 읽고, 날짜/시간/장소/인원수를 정리된 형식으로 재구성 (날짜 표기가 "26.6.28", "6월19일", "26년 6월 21일" 등 제각각이라 정규식보다 LLM이 해석하는 게 안정적)
- description까지 읽고 "용병 모집/팀원 모집/구장 양도" 등 실제로는 매칭글이 아닌 경우 한 번 더 걸러내기
- 매치 날짜가 실행일 기준 과거면 제외 (기간 필터)
- 결과를 Slack DM(MCP `slack_send_message`)으로 전송. Slack 도구에 표준 마크다운(`**bold**`)으로 입력하면 Slack 문법(`*bold*`)으로 자동 변환되니, 굳이 Slack 문법을 직접 쓰지 않아도 된다 (단, `*텍스트*`처럼 별표 1개로 직접 쓰면 이탤릭으로 변환되어버리니 주의)

## 자동 실행 (GitHub Actions, 사람 없이 서버에서 계속 돌리기)

Claude scheduled task와 달리 GitHub Actions는 LLM 없이 도는 순수 cron 환경이라, 날짜/시간/장소/인원수 해석을 `parse_match.py`의 정규식 기반 파서가 대신한다. 표기가 워낙 제각각이라 완벽하지 않고, 못 찾은 값은 "파악불가"로 안전하게 표시한다 (Claude 버전보다 정확도는 낮음).

### 구조

- `search_futsal.py` — 검색 + 1차 필터링(EXCLUDE_KEYWORDS) + 신규글 추적
- `parse_match.py` — 제목/description에서 날짜·시간·장소·인원수를 정규식으로 추출, 과거 매치 제외
- `notify_slack.py` — Slack Bot Token으로 메시지 발송. **수신자는 리스트라서 친구를 추가하려면 user ID 하나만 더 넣으면 됨**
- `run.py` — 위 셋을 묶어서 한 번에 실행하는 진입점 (GitHub Actions가 이걸 호출)
- `.github/workflows/notify.yml` — 3시간마다(`0 */3 * * *`) `run.py`를 실행하고, `seen_links.json` 변경분을 다시 레포에 커밋해서 다음 실행에 이어받는 워크플로우

### 1. Slack Bot 만들기

지금까지(개인 계정 DM)와 달리 GitHub Actions는 사람이 없는 서버에서 도니까 **개인 Slack 로그인 대신 Bot Token**이 필요하다.

1. https://api.slack.com/apps → "Create New App" → "From scratch"
2. 워크스페이스 선택 후 생성
3. 좌측 "OAuth & Permissions" → Bot Token Scopes에 `chat:write` 추가 (채널에만 보낼 거면 이거 하나로 충분. 개인 DM도 같이 쓸 거면 `im:write`도 추가)
4. 상단 "Install to Workspace" → 설치 → 발급된 **Bot User OAuth Token** (`xoxb-...`) 복사
5. 알림 보낼 채널(예: `#general`)에 이 봇을 초대한다 — Slack에서 그 채널 열고 `/invite @봇이름` 입력
6. 채널 ID 확인: 채널 이름 클릭 → 맨 아래 "채널 ID" 복사 (또는 채널 URL의 `C...` 부분)

### 2. GitHub repo에 Secrets 등록

레포 Settings → Secrets and variables → Actions → New repository secret:

| Secret | 값 |
|---|---|
| `NAVER_CLIENT_ID` | 네이버 API client ID |
| `NAVER_CLIENT_SECRET` | 네이버 API client secret |
| `SLACK_BOT_TOKEN` | 위에서 받은 `xoxb-...` |
| `SLACK_RECIPIENTS` | 알림 보낼 채널 ID, 쉼표로 여러 개 가능 (예: `C0XXXXXXXXX`). 특정 사람한테 DM으로도 보내고 싶으면 그 사람 user ID(`U...`)를 같이 나열하면 됨 |

채널로 보내면 그 채널에 있는 모든 사람(친구 포함)이 같은 알림을 보게 되므로, 친구를 추가하고 싶을 땐 **채널에 친구를 초대하기만 하면** 된다 (Secret을 다시 건드릴 필요 없음).

카페명/검색어/제외 키워드를 기본값과 다르게 쓰고 싶으면 (선택) Repository variables로 `TARGET_CAFE`, `SEARCH_QUERIES`, `EXCLUDE_KEYWORDS`도 추가하면 된다.

### 3. 친구에게도 보내기

채널 방식이면 **그 채널에 친구를 초대**하면 끝 — Secret을 다시 건드릴 필요 없다. 채널 말고 친구 개인 DM으로 따로 보내고 싶다면, `SLACK_RECIPIENTS`에 그 친구의 user ID를 쉼표로 추가하면 된다 (`C0XXXXXXX,U0YYYYYYY`처럼 채널과 유저 ID를 섞어 써도 됨). 코드 수정은 필요 없다 — `notify_slack.py`가 리스트의 각 대상에게 따로 발송한다.

### 4. 동작 확인

Actions 탭 → "Cafe match notifier" → "Run workflow"로 수동 실행해서 바로 테스트할 수 있다. 이후로는 cron이 3시간마다 자동으로 돈다.

### `seen_links.json`이 git에 커밋되는 이유

GitHub Actions는 매번 깨끗한 환경에서 시작하기 때문에, "이미 알려준 글" 기록을 어딘가에 저장해두지 않으면 매번 전체 글을 새 글로 오인한다. 그래서 워크플로우 마지막 단계에서 `seen_links.json` 변경분을 자동으로 커밋·푸시한다. (로컬에서 Claude scheduled task로 돌릴 때는 이 파일이 로컬에만 있어도 충분해서 `.gitignore`에 있었지만, GitHub Actions 버전에서는 git이 곧 "저장소" 역할을 하므로 추적 대상으로 바꿨다.)

## 파일 구성

- `search_futsal.py` — 검색 + 필터링 + 신규글 추적 스크립트 (단독 실행 가능, CLI로 출력만 봄)
- `parse_match.py` — 정규식 기반 날짜/시간/장소/인원수 파서 (GitHub Actions 경로에서 사용)
- `notify_slack.py` — Slack Bot Token 기반 다중 수신자 발송기
- `run.py` — search → parse → Slack 발송까지 한 번에 묻는 진입점
- `.github/workflows/notify.yml` — 3시간마다 자동 실행하는 GitHub Actions 워크플로우
- `AUTOMATION.md` — Claude scheduled task로 돌릴 때 쓴 지침 원문 (LLM 기반, GitHub Actions보다 해석 정확도가 높음)
- `.env.example` — 환경변수 템플릿 (`.env`는 git에 올리지 않음)
- `seen_links.json` — 이미 알려준 글의 링크 기록 (GitHub Actions가 자동으로 갱신·커밋함)
