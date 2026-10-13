# daily-briefing

관심 분야 소식을 **매일 아침 8시(한국시간)** 한 통의 지메일로 받는 자동화입니다.
8개 분야·34개 섹션에서 공식 RSS(또는 공식 API)만 읽어 섹션마다 2~3개씩 고르고, 월요일에는 메일 맨 위에
지난 7일을 정리한 **"이번 주 흐름"**이 붙습니다. 사이트를 크롤링하지 않습니다.

## 실행 구조

```
매일 08:00 KST (GitHub Actions, cron 0 23 * * * UTC)
 1. python -m src.collect   피드 수집 → 섹션마다 국내 1 + 해외 1 우선으로 고름 → data/briefing.json
                            (최근 5주 안에 보낸 글·같은 사건은 제외)
 2. python -m src.enrich    Claude에게 줄 입력 준비 (번역·요약 대상, 월요일엔 지난 7일 기록)
 3. Claude Code (1회 호출)   쉬운 한국어 제목·한 줄 설명·HN 쟁점·중복/광고 판단 (+ 월요일: 이번 주 흐름)
 4. python -m src.send      HTML 메일 생성·발송 → 오늘 실린 기사를 data/history/날짜.json에 저장
 5. 커밋                    data/history, data/trends를 저장소에 커밋 (다음 날 중복 방지·다음 주 비교에 사용)
```

- 메일 제목: 평소 `[데일리 브리핑] YYYY-MM-DD`, 월요일 `[데일리 브리핑 · 이번 주 흐름] YYYY-MM-DD`
- **수동 실행**: Actions → *Daily Briefing* → *Run workflow*. `dry_run`을 체크하면 발송·기록 커밋 없이
  미리보기(`preview.html`)만 아티팩트로 남깁니다. `weekly_trend`를 `on`으로 하면 요일과 상관없이 흐름을 만듭니다.
- 예약 실행은 기본 브랜치(main)의 워크플로만 동작합니다.

## 분야와 섹션 (메일 안 배치 순서)

| 분야 | 섹션 | 섹션당 |
| --- | --- | --- |
| 사고·지성 | 철학·담론 / 인지·심리 / AI 윤리·정렬 / 과학 일반 | 최대 3 |
| 문학 | 문학·비평 | 최대 3 |
| 미술 | 현대미술 비평 / 전시·미술 / 디자인·건축 / 사진·영상 / 시각문화 아카이브 | 최대 3 |
| AI·기술 | AI 업계 소식 / AI 실무 활용 / Hacker News / ML 논문 / 데이터 엔지니어링 / 보안·해킹 / IT 기기·서비스 | 최대 3 |
| 일 | 건설 IT·스마트건설 / ERP·SI 업계 / 프리랜서·원격근무 시장 | 최대 2 |
| 세상 | 국내 주요뉴스 / 해외 주요뉴스 / 오피니언 | 최대 2 |
| 경제·산업 | 경제·시장 / 산업·기업 / 노동·일자리 | 최대 2 |
| 생활 | 건강·의학 / 환경·기후 / 자동차·모빌리티 / 교육 / 여행 / 스포츠(KBL·NBA 포함) / 연예 / 문화·책 | 최대 2 |

- **국내 1 + 해외 1 우선**: 섹션마다 🇰🇷 국내 매체 기사 1개와 🌍 해외 매체 기사 1개를 먼저 고르고, 남은 자리는
  순위대로 채웁니다. 한쪽 매체만 있는 섹션은 있는 쪽에서 채웁니다. 기사마다 🇰🇷/🌍가 붙습니다.
- **새 소식 없음**: 고를 글이 없는 섹션은 "새 소식 없음" 한 줄로 표시합니다. 모든 섹션이 비면 메일을 보내지 않습니다.
- **볼 기간**: 분야마다 다릅니다(세상·경제 36시간, 생활 72시간, AI·기술 48시간, 사고·지성·미술·일 7일, 문학 14일).
  글이 드문 분야도 매일 채울 수 있게 길게 보되, **최근 5주 안에 메일에 실린 글은 다시 싣지 않습니다**.
- **목차**: 메일 위쪽에 8개 분야와 건수. 누르면 그 분야로 이동합니다.

## 월요일 "이번 주 흐름"

매일 메일에 실린 기사는 `data/history/YYYY-MM-DD.json`에 쌓이고(최근 5주치 유지), 월요일에 Claude가 지난 7일치를
읽어 세 층으로 정리합니다. 층마다 역할이 다르고, 각 줄은 🇰🇷 한국 / 🌍 세계로 나뉩니다.

| 층 | 줄 수 | 역할 | 위치 |
| --- | --- | --- | --- |
| 큰 방향 | 3줄 | 바깥 세상(세상·경제·산업·생활) / 기술과 일(AI·기술·일) / 사유와 예술(사고·지성·문학·미술)이 어느 쪽으로 가는지. 끝에 근거 분야 괄호 | 메일 맨 위 |
| 분야별 움직임 | 8줄 | 분야마다 이번 주 무엇이 늘고·바뀌고·부딪혔는지 | 메일 맨 위 |
| 섹션별 동향 | 34줄 | 섹션마다 이어진 구체적인 일들. 없으면 "이번 주 특별한 흐름 없음" | 메일 맨 아래 "섹션별 상세 동향" |

- 각 줄에 근거 기사 1~3개 링크(①②③). Claude는 기사 id만 고르고 실제 링크는 코드가 붙이므로 없는 링크가 생기지 않습니다.
- 지난주 흐름(`data/trends/`)과 비교해 🆕 새로 생김 / ➡️ 계속 / 🔻 줄어듦을 표시합니다. 첫 주는 표시하지 않습니다.
- Claude 단계가 실패하거나 결과가 없으면 흐름 없이 평소 메일로 보냅니다.
- 끄려면 저장소 Variables에 `WEEKLY_TREND` = `false`.

## 섹션을 다른 분야로 옮기는 법

`feeds.yaml`에서 섹션의 `group` 값만 바꾸면 됩니다. 섹션당 개수·볼 기간은 옮겨간 분야의 기본값을 따릅니다.

```yaml
  - key: science
    name: "과학 일반"
    group: thought      # ← tech로 바꾸면 "AI·기술" 분야로 옮겨갑니다
    feeds:
      - name: "Nature"
        url: "https://www.nature.com/nature.rss"
```

분야 순서·섹션당 개수·볼 기간은 `groups`에서, 이번 주 흐름의 큰 방향 3줄이 묶는 분야는 `trend_areas`에서 바꿉니다.

## `feeds.yaml` 설정 항목

```yaml
settings:
  history_days: 35            # 발송 기록 보관 기간 (이 기간 안에 보낸 글은 다시 안 실음)
  default_hours_back: 36
  max_html_kb: 100            # 메일 HTML 한도 (넘으면 기사가 많은 섹션부터 줄임)
  exclude_keywords: ["[광고]", "[보도자료]", Sponsored]   # 모든 섹션 공통 제외

groups:                       # 메일 안 순서 = 이 순서
  - {key: thought, name: "사고·지성", max_items: 3, hours_back: 168}

categories:
  - key: market               # 영문 식별자
    name: "경제·시장"           # 메일에 표시되는 섹션명
    group: economy            # 속한 분야
    max_items: 2              # (선택) 분야 기본값 대신
    hours_back: 36            # (선택) 분야 기본값 대신
    keywords: [금리, 환율]      # (선택) 제목에 하나라도 있어야 통과
    exclude_keywords: [연예]    # (선택) 제목에 하나라도 있으면 제외
    rank: coverage            # (선택) 여러 매체가 함께 다룬 사건 순 ("N개 매체 보도")
    summary_style: essay      # (선택) 장문 글: 한 줄 설명을 "무슨 주장·내용인지" 위주로
    feeds:
      - name: "연합뉴스 경제"
        url: "https://www.yna.co.kr/rss/economy.xml"
        region: kr            # (선택) 🇰🇷/🌍. 생략하면 이름에 한글이 있으면 kr
        hours_back: 504       # (선택) 글이 드문 피드만 기간을 따로
        user_agent: "curl/8.5.0"  # (선택) 기본 User-Agent를 막는 사이트용
```

- **키워드 매칭**: 영문/숫자 키워드(`SI`, `ERP`)는 대소문자 무시 + 단어 경계, 한글이 섞인 키워드는 포함 여부.
- **같은 사건 중복**: 메일 한 통 안에서 같은 링크·같은 사건은 한 번만(위쪽 섹션 우선). 제목 규칙으로 먼저 거르고,
  Claude가 표현·언어가 다른 중복(`dup_of`)과 광고·보도자료성 글(`ad`)을 한 번 더 거릅니다.
- **Hacker News**: 24시간 내 100점 이상, 포인트 순. **HF Daily Papers**: 추천 순.
- 피드가 죽었거나 RSS가 아니면 그 피드만 경고 로그를 남기고 건너뜁니다.

## 메일 형식

- 이미지 없이 최소한의 인라인 스타일만 씁니다. 본문 16px, 기사 제목 18px, 분야 제목 20px.
- 기사: 🇰🇷/🌍 + 쉬운 한국어 제목(원제는 아래 작게) + 출처·시각 + 한 줄 설명. 장문 에세이·비평 섹션은 "무슨 주장·내용인지" 위주.
- Hacker News: 한 줄 설명 + "찬성 쪽은 ~ / 반대 쪽은 ~" 댓글 쟁점.
- 지메일은 HTML이 102KB를 넘으면 잘라 보여주므로, 크기를 로그에 남기고 `max_html_kb`(100KB)를 넘으면 기사가 가장 많은
  섹션부터 하나씩 줄입니다.

## 발송 기록·예약 실행 유지

- 발송 후 `data/history/`(매일 실린 기사)와 `data/trends/`(월요일 흐름)를 워크플로가 저장소에 커밋합니다
  (`permissions: contents: write`). 35일이 지난 파일은 자동으로 지웁니다.
- 매일 커밋이 생기므로 "60일 무활동 시 예약 실행 중지"에 걸리지 않습니다. 발송이 멈춘 경우를 위해
  `keepalive.yml`(매월 1일 `last_run.txt` 커밋)도 그대로 둡니다.

## Secrets 등록 (메일 발송)

저장소 **Settings → Secrets and variables → Actions → New repository secret**에서 아래 3개를 등록하세요.

| Secret 이름 | 값 |
| --- | --- |
| `GMAIL_USER` | 보내는 지메일 주소 (예: `me@gmail.com`) |
| `GMAIL_APP_PASSWORD` | [Google 계정 → 보안 → 앱 비밀번호](https://myaccount.google.com/apppasswords)에서 발급한 16자리 앱 비밀번호 (2단계 인증 필요) |
| `MAIL_TO` | 받는 메일 주소 |

세 값이 모두 있어야 실제 발송이 일어납니다. 하나라도 없으면 `data/preview.html`만 만들고 발송·기록 저장은 건너뜁니다.

## Claude 옵션 (번역·요약·이번 주 흐름)

API 키 없이 Claude Pro/Max **구독** 토큰(`claude setup-token`)으로 GitHub Actions에서 Claude Code를 **실행당 한 번** 부릅니다
([Claude Code GitHub Actions](https://code.claude.com/docs/en/github-actions)). 토큰은 Secret `CLAUDE_CODE_OAUTH_TOKEN`으로 등록합니다.

| 변수 (Settings → Variables) | 기본 | 내용 |
| --- | --- | --- |
| `TRANSLATE_TITLES` | false | 영어 등 한글이 없는 제목을 쉬운 한국어로(원제는 아래 작게). 이름뿐인 한국어 제목은 풀어 씀 |
| `SUMMARIZE_ARTICLES` | false | 모든 글에 비개발자도 이해할 수 있는 한 줄 설명 (장문 섹션은 "무슨 주장인지") |
| `SUMMARIZE_HN` | false | HN 글마다 "무슨 일인지" 한 줄 + 찬성/반대 댓글 쟁점 |
| `WEEKLY_TREND` | **true** | 월요일 "이번 주 흐름" |

- 수동 실행 화면의 체크박스로도 켤 수 있습니다.
- Claude는 웹에 접속하지 않고, 수집 단계가 만든 파일(RSS 발췌문·HN 상위 댓글·발송 기록)만 읽고 결과 파일을 씁니다.
- Claude 단계가 실패해도 메일은 번역·요약·흐름 없이 그대로 발송됩니다.
- 이번 주 흐름은 지난 7일치 기록을 읽으므로, 배포 후 첫 월요일은 쌓인 날짜만큼만 반영됩니다.

## 로컬 실행

```bash
pip install -r requirements.txt
python -m src.collect --trend off      # auto(기본: 한국시간 월요일이면 흐름 포함) | on | off
python -m src.enrich                   # (선택) Claude 입력 준비
python -m src.send --dry-run           # data/preview.html만 생성 (크기 로그 출력)
```

## 피드 목록

2026-10-13에 GitHub Actions 러너에서 실제로 요청해서 응답을 확인한 공식 RSS/API만 넣었습니다.

| 분야 | 섹션 | 🇰🇷 국내 / 🌍 해외 |
| --- | --- | --- |
| 사고·지성 | 철학·담론 | 🌍 Astral Codex Ten, LessWrong(Curated), Aeon |
| 사고·지성 | 인지·심리 | 🇰🇷 정신의학신문 / 🌍 Psyche, Nautilus, PsyPost |
| 사고·지성 | AI 윤리·정렬 | 🇰🇷 AI타임스(윤리·안전 키워드) / 🌍 Alignment Forum, AI Safety Newsletter, AI as Normal Technology(AI Snake Oil) |
| 사고·지성 | 과학 일반 | 🇰🇷 헬로디디 / 🌍 Nature, Science, New Scientist, Quanta, Scientific American, NASA |
| 문학 | 문학·비평 | 🇰🇷 독서신문(문학 키워드) / 🌍 The Paris Review, LRB, NYRB |
| 미술 | 현대미술 비평 | 🇰🇷 아트코리아방송(평론) / 🌍 Artforum, Hyperallergic |
| 미술 | 전시·미술 | 🇰🇷 연합뉴스 문화, 뉴시스 문화, 서울문화투데이, 아트코리아방송, 아트인사이트 |
| 미술 | 디자인·건축 | 🇰🇷 에이앤씨뉴스, 월간 디자인 / 🌍 Dezeen, designboom, ArchDaily |
| 미술 | 사진·영상 | 🌍 Aperture, British Journal of Photography, PetaPixel |
| 미술 | 시각문화 아카이브 | 🌍 Colossal, Are.na Editorial |
| AI·기술 | AI 업계 소식 | 🇰🇷 AI타임스 / 🌍 OpenAI, Google DeepMind, Meta Newsroom, TechCrunch AI, The Verge AI |
| AI·기술 | AI 실무 활용 | 🇰🇷 GeekNews, AI타임스 / 🌍 AWS ML Blog, Google Cloud AI Blog, Microsoft Cloud Blog |
| AI·기술 | Hacker News | 🌍 Algolia HN API |
| AI·기술 | ML 논문 | 🌍 Hugging Face Daily Papers API |
| AI·기술 | 데이터 엔지니어링 | 🌍 Databricks, dbt Labs, Snowflake, AWS Big Data Blog, Data Engineering Weekly |
| AI·기술 | 보안·해킹 | 🇰🇷 보안뉴스, 데일리시큐 / 🌍 BleepingComputer, The Hacker News, Krebs on Security, The Record |
| AI·기술 | IT 기기·서비스 | 🇰🇷 전자신문, 지디넷코리아, 블로터 / 🌍 The Verge, Engadget, 9to5Mac, Android Authority |
| 일 | 건설 IT·스마트건설 | 🇰🇷 국토일보, 한국건설신문, 건설이코노미뉴스, 건설타임즈 / 🌍 Construction Dive, ENR |
| 일 | ERP·SI 업계 | 🇰🇷 전자신문, 디지털타임스, 아이티데일리, 지디넷코리아, 블로터, 바이라인네트워크, 한국경제 IT |
| 일 | 프리랜서·원격근무 시장 | 🌍 Freelancers Union, Reddit r/Upwork·r/freelance·r/remotework |
| 세상 | 국내 주요뉴스 | 🇰🇷 연합뉴스, SBS, 한국경제, 경향신문, 동아일보, 조선일보 |
| 세상 | 해외 주요뉴스 | 🇰🇷 연합뉴스 국제 / 🌍 BBC, Guardian, NYT, NPR, Al Jazeera, South China Morning Post, Deutsche Welle, France 24 |
| 세상 | 오피니언 | 🇰🇷 동아일보 사설, 경향·조선·한국경제·연합뉴스 오피니언 / 🌍 NYT Opinion, Guardian Opinion |
| 경제·산업 | 경제·시장 | 🇰🇷 연합뉴스, 한국경제, 매일경제 |
| 경제·산업 | 산업·기업 | 🇰🇷 연합뉴스 산업, 매일경제 기업, 전자신문 / 🌍 CNBC |
| 경제·산업 | 노동·일자리 | 🇰🇷 매일노동뉴스, 연합뉴스 경제 / 🌍 HR Dive, Guardian Work & careers |
| 생활 | 건강·의학 | 🇰🇷 연합뉴스 건강, 하이닥, 코메디닷컴 / 🌍 BBC Health, NYT Health, STAT, ScienceDaily |
| 생활 | 환경·기후 | 🇰🇷 뉴스펭귄, 이투뉴스, 그린포스트코리아, 에너지신문 / 🌍 Guardian, Carbon Brief, Inside Climate News, NYT Climate, Grist |
| 생활 | 자동차·모빌리티 | 🇰🇷 모터그래프, 오토헤럴드 / 🌍 Electrek, InsideEVs, TechCrunch Mobility, The Verge |
| 생활 | 교육 | 🇰🇷 한국교육신문, 에듀프레스, 베리타스알파 / 🌍 Hechinger Report, EdSurge, Guardian Education |
| 생활 | 여행 | 🇰🇷 여행신문, 트래블데일리, 투어코리아 / 🌍 Skift, Simple Flying, Guardian Travel |
| 생활 | 스포츠 | 🇰🇷 연합뉴스·한국경제 스포츠, 루키(KBL) / 🌍 BBC Sport, Guardian Sport, CBS Sports NBA, Yahoo Sports NBA |
| 생활 | 연예 | 🇰🇷 연합뉴스·뉴시스 연예 / 🌍 Variety, Hollywood Reporter, Billboard |
| 생활 | 문화·책 | 🇰🇷 연합·경향·동아 문화, 독서신문 / 🌍 Guardian Books·Film·Stage, NYT Books |

- 국토일보·한국건설신문·건설이코노미뉴스·오토헤럴드는 https 인증서 오류로 공식 RSS의 http 주소를 씁니다.
- 한국경제는 브라우저형 User-Agent를 막아 `user_agent: "curl/8.5.0"`으로 요청합니다.
- Reddit은 GitHub Actions에서 요청 제한(429)이 잦아 요청 사이에 15초 간격을 둡니다. 가끔 한두 곳이 빠질 수 있습니다.
- LRB·NYRB·Are.na Editorial은 글이 드물어 최근 3주까지 봅니다.

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
| Ribbonfarm (철학·담론) | RSS 주소가 아카이브 페이지로 이동 (RSS 없음) |
| Edge.org (철학·담론) | RSS 마지막 글이 2023-11 |
| e-flux Journal (현대미술 비평) | 저널 RSS 없음 (추정 주소 전부 404, 페이지에 RSS 링크 없음) |
| The Brooklyn Rail (현대미술 비평) | RSS 없음 |
| 국내 문학 웹진·문예지: 문장웹진, 창비, 문학동네, 릿터, 채널예스 (문학·비평) | RSS 없음 또는 응답 없음 → 출판 전문지 독서신문의 문학 기사(키워드)로 대신함 |
| 시사IN (참고) | RSS 마지막 글이 2024-06 |
| 씨네21 (문화·책) | RSS 주소가 로그인 페이지로 이동 |
| 점프볼·바스켓코리아 (스포츠, KBL) | RSS 응답 없음 → 농구 전문지 루키 + 연합뉴스 스포츠로 대신함 |
| ESPN (스포츠, NBA) | GitHub Actions에서 응답 없음 → CBS Sports·Yahoo Sports NBA로 대신함 |
| 한겨레 오피니언 (오피니언) | RSS에 날짜가 없어 기간 판단 불가 |
| 중앙일보 (오피니언 등) | RSS 없음 |
| 그리니엄, 에너지경제 (환경·기후) | RSS 응답 없음 |
| 글로벌오토뉴스, 한국경제 자동차 (자동차·모빌리티) | RSS 응답 없음 |
| 한국경제 산업·잡 (산업·기업, 노동·일자리) | 해당 RSS 없음 |
| It's Nice That (시각문화 아카이브) | 공식 RSS 주소가 응답하지 않음 |
| Import AI, BPS Research Digest (AI 윤리·정렬, 인지·심리) | RSS 응답 없음 |
| 월간사진, 사진예술 (사진·영상) | RSS 없음 또는 응답 없음 → 사진·영상은 해외 매체만 |
| 디자인정글, SPACE(공간) (디자인·건축) | RSS 없음 → 국내는 월간 디자인·에이앤씨뉴스로 대신함 |
| 마인드포스트, 브레인미디어 (인지·심리) | https 인증서 오류 / 응답 없음 → 국내는 정신의학신문으로 대신함 |
| 국내 철학·담론, AI 정렬, 시각문화 아카이브 매체 | RSS가 있는 적당한 국내 매체를 찾지 못함 → 해외 매체만 (국내 1개 + 해외 1개 규칙에서 한쪽만 있는 섹션) |

