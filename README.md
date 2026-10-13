# daily-weekly-briefing

관심 분야 뉴스의 제목·링크·출처·날짜를 모아 지메일로 보내는 자동화입니다.
**데일리**(매일 아침, 최근 24시간)와 **주간**(월요일 아침, 최근 7일) 두 가지가 있고,
월요일에는 둘을 한 통으로 합쳐 보냅니다. RSS(공식 피드만), Hugging Face Daily Papers API,
Hacker News(Algolia API)만 사용하며 사이트를 크롤링하지 않습니다. 요약은 기본적으로 꺼져 있습니다.

## 발송 일정

| 언제 (한국시간) | 메일 제목 | 내용 |
| --- | --- | --- |
| 화~일 오전 8:00 | `[데일리 브리핑] YYYY-MM-DD` | 데일리 분야 (최근 24시간) |
| 월 오전 8:00 | `[데일리+주간 브리핑] YYYY-MM-DD` | 위에 데일리, 아래에 주간 분야 (최근 7일) |

- `.github/workflows/briefing.yml`의 cron은 UTC 기준 `0 23 * * *` (= 한국시간 매일 08:00) 하나입니다.
  실행 시점의 한국시간 요일이 월요일이면 자동으로 데일리+주간(`both`), 그 외에는 데일리만 보냅니다.
- **수동 실행**: Actions → *Daily + Weekly Briefing* → *Run workflow*에서 `daily` / `weekly` / `both`를
  고를 수 있습니다. `dry_run`을 체크하면 메일은 보내지 않고 미리보기 HTML만 아티팩트로 남깁니다.
  (`weekly`만 수동으로 보내면 제목은 `[주간 브리핑] YYYY-MM-DD`)
- 예약 실행은 기본 브랜치(main)에 있는 워크플로만 동작합니다. 이 브랜치를 main에 병합해야 일정이 적용됩니다.

## 분야 구성

메일에는 `feeds.yaml`에 적힌 순서대로 표시됩니다.

**데일리** (분야별 최대 5개)

1. AI·데이터 도구
2. ML 논문 — HF Daily Papers 추천 상위 3개
3. 국내 경제·제도 — 제목 키워드 필터
4. 국내 IT 정책·업계 — 제목 키워드 필터
5. Hacker News — 24시간 내 100점 이상, 포인트 상위 5개 (기사 링크 + HN 댓글 링크)

**주간** (따로 적지 않으면 분야별 최대 10개)

1. DB·데이터 엔지니어링
2. 프리랜서·업워크 시장
3. 과학·수학
4. 생각·인문
5. 책·서평
6. 미술
7. 건축·공간 — 설치·전시·공간 연출 키워드 필터, 최대 5개

전체 피드 목록과 제외된 사이트는 아래 [피드 목록](#피드-목록)을 참고하세요.

## 분야를 데일리 ↔ 주간으로 옮기는 법

`feeds.yaml`에서 해당 분야의 `schedule` 값만 바꾸면 됩니다.

```yaml
  - key: science_math
    name: "과학·수학"
    schedule: weekly     # ← daily로 바꾸면 다음 날부터 데일리 메일에 들어갑니다
    feeds:
      - name: "Quanta Magazine"
        url: "https://www.quantamagazine.org/feed/"
```

- 옮기면 기간도 함께 바뀝니다(데일리 24시간 / 주간 7일, `schedules.<daily|weekly>.hours_back`).
- 분야에 `max_items`를 적지 않았다면 개수도 옮겨간 쪽 기본값을 따릅니다
  (`schedules.daily.default_max_items: 5`, `schedules.weekly.default_max_items: 10`).
- 메일 속 순서는 파일 안의 순서입니다. 데일리 묶음/주간 묶음 안에서 위치를 바꾸고 싶으면 블록을 옮기면 됩니다.

## `feeds.yaml` 설정 항목

```yaml
settings:
  max_html_kb: 100          # 메일 HTML 한도 (넘으면 자동으로 개수를 줄임)

schedules:
  daily:  { title: "데일리 브리핑", hours_back: 24,  default_max_items: 5 }
  weekly: { title: "주간 브리핑",   hours_back: 168, default_max_items: 10 }

categories:
  - key: kr_economy               # 영문 식별자 (목차 링크용)
    name: "국내 경제·제도"          # 메일에 표시되는 분야명
    schedule: daily               # daily | weekly
    type: rss                     # rss(기본) | hf_papers | hacker_news
    max_items: 5                  # 분야 최대 개수
    keywords: [금리, 환율, 부동산]  # 제목에 하나라도 있으면 통과 (생략하면 필터 없음)
    feeds:
      - name: "연합뉴스 경제"
        url: "https://www.yna.co.kr/rss/economy.xml"
        max_items: 3              # (선택) 이 피드에서 최대 몇 개
        keywords: [...]           # (선택) 이 피드에만 다른 키워드 적용
```

- **키워드 매칭**: 영문/숫자로만 된 키워드(`SI`, `ERP`, `PostgreSQL`)는 대소문자 무시 + 단어 경계 기준이라
  `SI`가 `ASIA`, `SIM` 안에서 걸리지 않습니다. 한글이 섞인 키워드는 제목에 포함되면 통과합니다.
- **한 분야 안의 선택 방식**: 피드별 최신 글을 번갈아 골라서(한 피드가 분야를 독차지하지 않게) 최대 개수를
  채운 뒤 최신순으로 보여줍니다. 같은 링크·같은 제목은 한 번만 나옵니다.
- **Hacker News**: `min_points`(기본 100)와 `max_items`를 분야에 적습니다. 기간은 분야의 schedule을 따릅니다.
- **HF Daily Papers**: 기간 안에 Daily Papers에 올라온 논문 중 추천(upvotes) 순으로 `max_items`개.
- 피드가 죽었거나 RSS가 아니면 그 피드만 경고 로그를 남기고 건너뜁니다.

## 메일 형식

- 맨 위에 **목차**(분야명 + 건수). 누르면 해당 섹션으로 이동합니다.
- 기간 안에 글이 없는 분야는 섹션째 생략, **모든 분야가 비면 메일을 보내지 않습니다.**
- 이미지 없이 최소한의 인라인 스타일만 씁니다. 지메일은 HTML이 102KB를 넘으면 뒷부분을 잘라 보여주므로,
  생성된 HTML 크기를 로그에 출력하고 `settings.max_html_kb`(기본 100KB)를 넘으면 글이 가장 많은 분야부터
  하나씩 줄여서 맞춥니다(줄인 결과도 로그에 남김).

## 예약 실행 유지 (keepalive)

공개 저장소는 60일간 커밋이 없으면 GitHub가 예약 워크플로를 자동으로 끕니다.
`.github/workflows/keepalive.yml`이 매월 1일(한국시간 09:00) `last_run.txt`에 날짜를 기록해 커밋하므로
예약 실행이 꺼지지 않습니다(`permissions: contents: write`). Actions 탭에서 수동 실행도 됩니다.

## Secrets 등록 (메일 발송)

저장소 **Settings → Secrets and variables → Actions → New repository secret**에서 아래 3개를 등록하세요.
(기존과 동일)

| Secret 이름 | 값 |
| --- | --- |
| `GMAIL_USER` | 보내는 지메일 주소 (예: `me@gmail.com`) |
| `GMAIL_APP_PASSWORD` | [Google 계정 → 보안 → 앱 비밀번호](https://myaccount.google.com/apppasswords)에서 발급한 16자리 앱 비밀번호 (2단계 인증 필요) |
| `MAIL_TO` | 받는 메일 주소 |

세 값이 모두 있어야 실제 발송이 일어납니다. 하나라도 없으면 `data/preview.html`만 만들고 발송은 건너뜁니다.

## 요약 옵션 (기본 꺼짐)

API 키 없이 Claude Pro/Max **구독** 토큰(`claude setup-token`)으로 GitHub Actions에서 Claude Code를 실행해
요약을 붙일 수 있습니다([Claude Code GitHub Actions](https://code.claude.com/docs/en/github-actions)).

1. 로컬에서 `claude setup-token` → 출력된 토큰을 Secret `CLAUDE_CODE_OAUTH_TOKEN`으로 등록
2. 켜기
   - 수동 실행: Run workflow 화면의 `summarize_articles`, `summarize_hn` 체크박스
   - 예약 실행: **Settings → Secrets and variables → Actions → Variables**에 `SUMMARIZE_ARTICLES`,
     `SUMMARIZE_HN`을 `true`로 등록

| 요약 | 내용 |
| --- | --- |
| `SUMMARIZE_ARTICLES` | Hacker News를 뺀 모든 글에 한국어 한 줄 요약 |
| `SUMMARIZE_HN` | HN 글마다 상위 댓글 20~30개를 읽고 쟁점·주요 반론 3~4줄 요약 |

이제 매일 실행되므로, 요약을 켜면 구독 사용량도 매일 소모됩니다. 둘 다 꺼져 있으면 토큰은 전혀 쓰이지 않습니다.

## 로컬 실행

```bash
pip install -r requirements.txt
python -m src.collect --mode daily     # daily | weekly | both | auto(기본: 한국시간 월요일이면 both)
python -m src.send --dry-run           # data/preview.html만 생성 (크기 로그 출력)
```

`GMAIL_USER`, `GMAIL_APP_PASSWORD`, `MAIL_TO` 환경변수를 설정하고 `--dry-run` 없이 실행하면 실제로 발송합니다.

## 피드 목록

2026-10-13에 GitHub Actions 러너에서 실제로 요청해서 동작을 확인한 피드만 넣었습니다.

| 구분 | 분야 | 피드 |
| --- | --- | --- |
| 데일리 | AI·데이터 도구 | GeekNews, Simon Willison, Hugging Face Blog, OpenAI News, Google DeepMind, AI타임스, AWS Big Data Blog |
| 데일리 | ML 논문 | Hugging Face Daily Papers API |
| 데일리 | 국내 경제·제도 | 연합뉴스 경제·마켓, 한국경제 경제·금융·부동산, 매일경제 경제·부동산 |
| 데일리 | 국내 IT 정책·업계 | 지디넷코리아, 블로터, 바이라인네트워크, 한국경제 IT |
| 데일리 | Hacker News | Algolia HN API |
| 주간 | DB·데이터 엔지니어링 | Planet PostgreSQL, SQLBI, Power BI Blog, Data Engineering Weekly, 토스 기술블로그, 카카오 기술블로그 |
| 주간 | 프리랜서·업워크 시장 | Freelancers Union Blog, Reddit r/Upwork 주간 상위(최대 5) |
| 주간 | 과학·수학 | Quanta Magazine |
| 주간 | 생각·인문 | Astral Codex Ten, Aeon, Psyche, Noema Magazine, LessWrong Curated |
| 주간 | 책·서평 | Five Books |
| 주간 | 미술 | Colossal, Hyperallergic(최대 5), Artforum, 아트코리아방송(최대 5), 아트인사이트(미술 키워드, 최대 3) |
| 주간 | 건축·공간 | Dezeen, ArchDaily (설치·전시·공간 키워드, 최대 5) |

### 제외한 사이트

| 사이트 | 이유 |
| --- | --- |
| 전자신문 | RSS(`rss.etnews.com`)는 있지만 GitHub Actions 러너(해외 IP)에서 연결이 시간 초과 |
| Oracle Database Insider 블로그 | GitHub Actions에서 403 (봇 차단) |
| 우아한형제들 기술블로그 | GitHub Actions에서 403 (봇 차단) |
| Frieze | 사이트 전체가 GitHub Actions에서 403 (봇 차단) |
| Upwork Research Institute | RSS 없음 (페이지도 403) |
| e-flux Journal | 저널 전용 RSS 없음 (자동탐색 링크 없음, 추정 주소 전부 404) |
| 국립현대미술관(MMCA) | RSS 없음 |
| 아트인컬처 | RSS 없음 |
| 월간미술 | RSS는 있지만 마지막 글이 2020-07 |
| 채널예스 | RSS 없음 |
| Edge.org | RSS는 있지만 마지막 글이 2023-11 |
| Ribbonfarm | `/feed/`가 아카이브 페이지로 리다이렉트됨 (RSS 없음) |

봇 차단으로 빠진 곳(전자신문, Oracle, 우아한형제들, Frieze)은 사이트 정책이 바뀌면 `feeds.yaml`에 다시
넣어볼 수 있습니다. 실패해도 그 피드만 경고 로그를 남기고 건너뜁니다.
