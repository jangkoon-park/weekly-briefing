# daily-weekly-briefing

관심 분야 뉴스의 제목·링크·출처·날짜를 모아 지메일로 보내는 자동화입니다.
**데일리**(매일 아침, 최근 24시간)와 **주간**(월요일 아침, 최근 7일) 두 가지가 있고,
월요일에는 둘을 한 통으로 합쳐 보냅니다. RSS(공식 피드만), Hugging Face Daily Papers API,
Hacker News(Algolia API)만 사용하며 사이트를 크롤링하지 않습니다. 제목 번역과 요약은 기본적으로 꺼져 있습니다.

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

**데일리** (매일 아침 8시, 최근 24시간, 섹션당 최대 5개)

1. 국내 주요뉴스 — 정치·경제·사회. 여러 매체가 함께 다룬 사건 순 ("N개 매체 보도"), 연예·스포츠 제외
2. 해외 주요뉴스 — 국제·경제 위주, 여러 매체가 함께 다룬 사건 순
3. 경제·시장 — 금리·환율·증시·부동산 키워드, 여러 매체가 함께 다룬 사건 순
4. AI 업계 소식 — OpenAI·Google DeepMind·Meta 공식 소식 + Anthropic 등 빅테크 관련 기사 + 국내 AI 뉴스
5. Hacker News — 24시간 내 100점 이상, 포인트 상위 5개 (한 줄 설명 + 댓글 찬반 쟁점)
6. ML 논문 — HF Daily Papers 추천 상위 3개

**주간** (월요일 데일리와 한 통으로, 최근 7일, 섹션당 최대 7개)

1. 데이터 엔지니어링 — Databricks, dbt, Snowflake, AWS 데이터 블로그 등
2. AI 실무 활용 — RAG·에이전트·기업 도입 사례 키워드
3. 건설 IT·스마트건설 — 국내 건설 전문지 + ENR·Construction Dive (스마트건설·BIM·AI 등 키워드)
4. ERP·SI 업계 — 국내 IT 매체에서 SI·ERP·IT서비스 기업 키워드
5. 프리랜서·원격근무 시장 — Freelancers Union, Reddit 업워크·프리랜서·원격근무 커뮤니티 주간 상위 글
6. 전시·미술 — 국내 언론 문화면·미술 매체에서 전시 관련 기사
7. 과학 일반 — Nature·Science 등, 여러 매체가 함께 다룬 발견 순

전체 피드 목록과 "후보 없음" 사유는 아래 [피드 목록](#피드-목록)을 참고하세요.

## 분야를 데일리 ↔ 주간으로 옮기는 법

`feeds.yaml`에서 해당 분야의 `schedule` 값만 바꾸면 됩니다.

```yaml
  - key: science
    name: "과학 일반"
    schedule: weekly     # ← daily로 바꾸면 다음 날부터 데일리 메일에 들어갑니다
    feeds:
      - name: "Nature"
        url: "https://www.nature.com/nature.rss"
```

- 옮기면 기간도 함께 바뀝니다(데일리 24시간 / 주간 7일, `schedules.<daily|weekly>.hours_back`).
- 분야에 `max_items`를 적지 않았다면 개수도 옮겨간 쪽 기본값을 따릅니다
  (`schedules.daily.default_max_items: 5`, `schedules.weekly.default_max_items: 7`).
- 메일 속 순서는 파일 안의 순서입니다. 데일리 묶음/주간 묶음 안에서 위치를 바꾸고 싶으면 블록을 옮기면 됩니다.

## `feeds.yaml` 설정 항목

```yaml
settings:
  max_html_kb: 100          # 메일 HTML 한도 (넘으면 자동으로 개수를 줄임)

schedules:
  daily:  { title: "데일리 브리핑", hours_back: 24,  default_max_items: 5 }
  weekly: { title: "주간 브리핑",   hours_back: 168, default_max_items: 7 }

categories:
  - key: market                   # 영문 식별자 (목차 링크용)
    name: "경제·시장"               # 메일에 표시되는 분야명
    schedule: daily               # daily | weekly
    type: rss                     # rss(기본) | hf_papers | hacker_news
    max_items: 5                  # 분야 최대 개수
    keywords: [금리, 환율, 부동산]  # 제목에 하나라도 있으면 통과 (생략하면 필터 없음)
    exclude_keywords: [연예]       # 제목에 하나라도 있으면 제외
    rank: coverage                # 여러 매체가 함께 다룬 사건 순 (생략하면 피드별로 번갈아 고른 뒤 최신순)
    similarity: 0.5               # (선택) 같은 사건으로 볼 제목 글자 겹침 기준
    feeds:
      - name: "연합뉴스 경제"
        url: "https://www.yna.co.kr/rss/economy.xml"
        max_items: 3              # (선택) 이 피드에서 최대 몇 개
        keywords: [...]           # (선택) 이 피드에만 다른 키워드 적용
```

- **키워드 매칭**: 영문/숫자로만 된 키워드(`SI`, `ERP`, `PostgreSQL`)는 대소문자 무시 + 단어 경계 기준이라
  `SI`가 `ASIA`, `SIM` 안에서 걸리지 않습니다. 한글이 섞인 키워드는 제목에 포함되면 통과합니다.
- **한 분야 안의 선택 방식**: 기본은 피드별 최신 글을 번갈아 골라서(한 피드가 분야를 독차지하지 않게) 최대 개수를
  채운 뒤 최신순으로 보여줍니다. `rank: coverage`면 같은 사건을 다룬 기사끼리 묶어 여러 매체가 다룬 사건부터
  보여주고(대표 기사는 feeds 목록에서 먼저 적힌 피드), "N개 매체 보도"를 표시합니다.
- **중복 제거**: 같은 링크, 같은 사건으로 판단된 기사는 메일 한 통에서 한 번만 나옵니다(위쪽 분야 우선).
- **Hacker News**: `min_points`(기본 100)와 `max_items`를 분야에 적습니다. 기간은 분야의 schedule을 따릅니다.
- **HF Daily Papers**: 기간 안에 Daily Papers에 올라온 논문 중 추천(upvotes) 순으로 `max_items`개.
- 피드가 죽었거나 RSS가 아니면 그 피드만 경고 로그를 남기고 건너뜁니다.

## 메일 형식

- 맨 위에 **목차**(분야명 + 건수). 누르면 해당 섹션으로 이동합니다.
- **같은 사건 중복은 하나만**: 메일 한 통(월요일 합본 포함) 안에서 같은 링크나 같은 사건을 다룬 기사는 위쪽 분야에
  한 번만 나옵니다. 제목 비교로 먼저 거르고(같은 주어 + 공통 핵심 단어 등), 번역·요약 옵션이 켜져 있으면 Claude가
  표현이나 언어가 다른 중복을 한 번 더 거릅니다(`dup_of`).
- 기간 안에 글이 없는 분야는 섹션째 생략, **모든 분야가 비면 메일을 보내지 않습니다.**
- 휴대폰에서 읽기 편하도록 본문 16px, 기사 제목 18px, 분야 제목 20px.
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

## 번역·요약 옵션 (기본 꺼짐)

API 키 없이 Claude Pro/Max **구독** 토큰(`claude setup-token`)으로 GitHub Actions에서 Claude Code를 실행해
제목 번역과 요약을 붙일 수 있습니다([Claude Code GitHub Actions](https://code.claude.com/docs/en/github-actions)).
세 가지는 각각 따로 켜고 끕니다.

| 변수 | 내용 |
| --- | --- |
| `TRANSLATE_TITLES` | 한글이 없는 제목(영어 등)을 한국어로 번역해 링크로 보여주고, 원제는 그 아래 작은 글씨로 표시. 한국어 제목은 그대로 두되 제품·회사 이름뿐이면 내용이 드러나게 풀어 씀 |
| `SUMMARIZE_ARTICLES` | Hacker News를 뺀 모든 글에 비개발자도 이해할 수 있는 쉬운 말 한 줄 요약 (전문용어는 풀어서) |
| `SUMMARIZE_HN` | HN 글마다 상위 댓글 20개를 참고해 ① "무슨 일인지" 쉬운 한 줄 설명, ② 그 아래 "찬성 쪽은 ~ / 반대 쪽은 ~" 두 줄 쟁점 요약 |

1. 로컬에서 `claude setup-token` → 출력된 토큰을 Secret `CLAUDE_CODE_OAUTH_TOKEN`으로 등록
2. 켜기
   - 수동 실행: Run workflow 화면의 `translate_titles`, `summarize_articles`, `summarize_hn` 체크박스
   - 예약 실행: **Settings → Secrets and variables → Actions → Variables**에 위 변수를 `true`로 등록

**동작 방식 (Claude 호출은 실행당 한 번)**

1. `python -m src.enrich`가 켜진 옵션에 맞춰 필요한 기사만 골라 `data/enrich_input.json`과 지시문
   `data/enrich_prompt.md`를 만듭니다. 요약은 RSS에 들어 있는 기사 앞부분 발췌문을, HN 요약은 여기서 미리
   받아 둔 상위 댓글을 근거로 하므로 Claude가 웹에 접속할 필요가 없습니다.
2. Claude Code가 **한 번** 실행되어 파일만 읽고(`Read`) 번역·요약·댓글 요약을 모두 `data/enrich.json`에 씁니다.
3. 발송 단계가 결과를 메일에 반영합니다. Claude 단계가 실패해도 메일은 번역·요약 없이 그대로 발송됩니다.

요약 공통 규칙: 제목이 제품·회사·프로젝트 이름뿐이면 그게 무엇인지 풀어서 쓰고(예: "뮤즈 원더: ○○사가 새로 낸
AI 모델"), 발췌문·댓글로도 알 수 없으면 "원문 확인 필요"라고만 표시합니다.

세 옵션이 모두 꺼져 있거나 대상 기사가 없으면 Claude 단계는 아예 실행되지 않습니다(구독 사용량 소모 없음).
매일 실행되므로, 켜 두면 구독 사용량이 매일 조금씩 소모됩니다.

## 로컬 실행

```bash
pip install -r requirements.txt
python -m src.collect --mode daily     # daily | weekly | both | auto(기본: 한국시간 월요일이면 both)
python -m src.send --dry-run           # data/preview.html만 생성 (크기 로그 출력)
```

`GMAIL_USER`, `GMAIL_APP_PASSWORD`, `MAIL_TO` 환경변수를 설정하고 `--dry-run` 없이 실행하면 실제로 발송합니다.

## 피드 목록

2026-10-13에 GitHub Actions 러너에서 실제로 요청해서 응답을 확인한 공식 RSS/API만 넣었습니다.

| 구분 | 섹션 | 피드 |
| --- | --- | --- |
| 데일리 | 국내 주요뉴스 | 연합뉴스 정치·사회·경제, SBS 정치·사회, 한국경제 정치, 경향신문, 동아일보, 조선일보 |
| 데일리 | 해외 주요뉴스 | BBC World·Business, Guardian World, NYT World·Business, NPR World, Al Jazeera, 연합뉴스 국제 |
| 데일리 | 경제·시장 | 연합뉴스 경제·마켓, 한국경제 경제·금융·부동산, 매일경제 경제·부동산 |
| 데일리 | AI 업계 소식 | OpenAI News, Google DeepMind, Meta Newsroom(AI 키워드), TechCrunch AI·The Verge AI(빅테크 AI 키워드), AI타임스 |
| 데일리 | Hacker News | Algolia HN API |
| 데일리 | ML 논문 | Hugging Face Daily Papers API |
| 주간 | 데이터 엔지니어링 | Databricks Blog, dbt Labs Blog, Snowflake Blog, AWS Big Data Blog, Data Engineering Weekly |
| 주간 | AI 실무 활용 | AWS Machine Learning Blog, Google Cloud AI Blog, Microsoft Cloud Blog, GeekNews, AI타임스 (RAG·에이전트·도입 사례 키워드) |
| 주간 | 건설 IT·스마트건설 | 국토일보, 한국건설신문, 건설이코노미뉴스, 건설타임즈, Construction Dive(Technology), ENR |
| 주간 | ERP·SI 업계 | 전자신문, 디지털타임스 ICT, 아이티데일리, 지디넷코리아, 블로터, 바이라인네트워크, 한국경제 IT |
| 주간 | 프리랜서·원격근무 시장 | Freelancers Union Blog, Reddit r/Upwork·r/freelance·r/remotework 주간 상위 |
| 주간 | 전시·미술 | 연합뉴스 문화, 뉴시스 문화, 서울문화투데이, 아트코리아방송, 아트인사이트 (전시 키워드) |
| 주간 | 과학 일반 | Nature, Science, New Scientist, Quanta Magazine, Scientific American, NASA, 헬로디디 |

- 국토일보·한국건설신문·건설이코노미뉴스는 https 인증서 오류로 공식 RSS의 http 주소를 씁니다.
- 한국경제는 브라우저형 User-Agent를 막아 `user_agent: "curl/8.5.0"`으로 요청합니다.
- Reddit은 GitHub Actions에서 요청 제한(429)이 잦아 요청 사이에 15초 간격을 둡니다. 그래도 가끔 한두 곳이 빠질 수 있습니다.

### 후보 없음 / 제외한 사이트

| 사이트·섹션 | 이유 |
| --- | --- |
| Anthropic 공지 (AI 업계 소식) | 공식 RSS 없음. TechCrunch·The Verge의 Anthropic·Claude 관련 기사로 대신함 |
| LangChain·LlamaIndex 블로그 (AI 실무 활용) | 공식 RSS 없음 (RSS 주소가 블로그 페이지로 이동) |
| 대한경제(건설경제) (건설 IT) | RSS 없음 |
| 국토교통부 보도자료 (건설 IT) | RSS 주소가 응답하지 않음 |
| Upwork·Fiverr IR, Upwork Research Institute (프리랜서) | RSS 없음 또는 GitHub Actions에서 403. 업워크 공식 소식은 넣지 못함 |
| FlexJobs 블로그 (프리랜서·원격근무) | GitHub Actions에서 응답 시간 초과 |
| 국립현대미술관·서울시립미술관·리움 등 서울 주요 미술관 (전시·미술) | 공식 RSS 없음. 미술관 전시 소식은 언론 문화면의 전시 기사로 대신함. 서울 열린데이터광장·문화포털의 전시 정보 API는 공식 API지만 인증키 발급이 필요해 이번엔 넣지 않음 |
| 아트인컬처, 월간미술 (전시·미술) | RSS 없음 / 마지막 글 2020년 |
| 동아사이언스, 사이언스타임즈 (과학 일반) | RSS 없음 또는 응답 없음 → 국내 과학 소식은 헬로디디로 대신함 |
| 한겨레 (국내 주요뉴스) | RSS에 날짜가 없어 "최근 24시간" 판단 불가 |
| JTBC (국내 주요뉴스) | RSS 마지막 글이 2024년 |
