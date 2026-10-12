# weekly-news-briefing

AI·데이터, 프리랜서·업워크 시장, 건설IT·ERP 분야 뉴스를 매주 월요일 아침 지메일로 모아 받는 자동화입니다.
RSS(공식 피드만)와 Hacker News(Algolia API)에서 제목·링크·출처·날짜만 모아 보내며, 요약은 기본적으로 꺼져 있습니다.

## 동작 방식

1. **수집** (`python -m src.collect`): `feeds.yaml`에 등록된 RSS 피드와 Hacker News(Algolia API)를 읽어
   최근 7일 기사만, 중복 링크 제거, 분야별 최대 10개로 걸러 `data/articles.json`, `data/hn.json`에 저장합니다.
2. **(선택) 요약**: GitHub Actions에서 `anthropics/claude-code-action`을 이용해 Claude Pro/Max 구독 토큰으로
   요약을 생성하고 `data/summaries.json`, `data/hn_summaries.json`에 저장합니다. 기본은 꺼져 있고, 이 단계를
   건너뛰면 아예 실행되지 않습니다(토큰/구독 사용량 소모 없음).
3. **발송** (`python -m src.send`): 위 데이터를 모바일 친화적인 HTML로 만들어 `data/preview.html`에 저장하고,
   Gmail 계정 정보(Secrets)가 모두 있으면 메일로 발송합니다. 하나라도 없으면 발송하지 않고 미리보기 파일만 남깁니다(dry-run).

## 피드 추가/삭제 (`feeds.yaml`)

```yaml
categories:
  - key: ai_data
    name: "AI·데이터 도구"
    feeds:
      - name: "GeekNews"
        url: "https://news.hada.io/rss/news"
        lang: ko
```

- `categories` 아래에 분야를 추가/삭제할 수 있습니다. `key`는 영문 식별자, `name`은 메일에 표시되는 분야명입니다.
- 각 분야의 `feeds` 목록에 `name`(출처로 표시됨)과 `url`(RSS/Atom 주소)만 있는 항목을 추가/삭제하면 됩니다.
- `settings.days_back`(기본 7), `settings.max_items_per_category`(기본 10)로 기간/개수를 바꿀 수 있습니다.
- `hacker_news.min_points`(기본 200), `hacker_news.days_back`(기본 7), `hacker_news.max_items`(기본 5)로 HN 조건을 바꿀 수 있습니다.
- **공식 RSS만 등록하세요.** 사이트를 직접 크롤링하는 기능은 없습니다. 등록한 피드가 죽어 있거나 RSS가 아니면
  해당 피드만 경고 로그를 남기고 건너뛰고, 전체 실행은 계속됩니다.

### 피드 조사 결과 (이번 설정에서 못 넣은 것들)

요청하신 사이트 중 아래 두 곳은 **공식 RSS가 없어서** `feeds.yaml`에 넣지 못했습니다 (크롤링은 하지 않는다는
원칙 때문입니다):

- **Anthropic 공지(anthropic.com/news)**: 페이지에 RSS/Atom 링크가 없습니다. 공식 RSS가 생기면 `feeds.yaml`의
  `ai_data.feeds`에 추가하면 됩니다.
- **Upwork 블로그**: Upwork가 2024년 8월 RSS 기능을 전면 종료했습니다(공식 고객센터 공지). 블로그용 별도
  피드도 확인되지 않았습니다.

대신 아래 피드들로 각 분야를 구성했습니다 (전부 공식 RSS):

| 분야 | 피드 |
| --- | --- |
| AI·데이터 도구 | GeekNews, OpenAI News, Hugging Face Blog, AWS Big Data Blog, Simon Willison's Weblog(LLM 태그) |
| 프리랜서·업워크 시장 | Freelancers Union Blog |
| 건설IT·ERP | Engineering News-Record(ENR), Construction Dive |

> 이 작업을 진행한 샌드박스 환경은 네트워크가 Anthropic 도메인 위주로 제한되어 있어, 위 피드들이 실제로
> 응답하는지 이 환경에서는 직접 확인하지 못했습니다(아래 "검증 관련 안내" 참고). push 후 Actions 탭에서
> `workflow_dispatch`로 한 번 수동 실행해서 `data/articles.json`에 각 분야 기사가 채워지는지 확인해보세요.
> 특정 피드가 하나라도 응답하지 않아도 전체 실행은 멈추지 않고 로그에 경고만 남습니다.
>
> 프리랜서 분야는 공식 RSS를 운영하는 곳이 특히 적었습니다. 괜찮은 소스를 알고 계시면 `feeds.yaml`에
> 자유롭게 추가해주세요.

## Secrets 등록 (메일 발송)

저장소 **Settings → Secrets and variables → Actions → New repository secret**에서 아래 3개를 등록하세요.

| Secret 이름 | 값 |
| --- | --- |
| `GMAIL_USER` | 보내는 지메일 주소 (예: `me@gmail.com`) |
| `GMAIL_APP_PASSWORD` | [Google 계정 → 보안 → 앱 비밀번호](https://myaccount.google.com/apppasswords)에서 발급한 16자리 앱 비밀번호 (2단계 인증 필요) |
| `MAIL_TO` | 받는 메일 주소 |

세 값이 모두 등록되어 있어야 실제 발송이 일어납니다. 하나라도 없으면 `data/preview.html`만 생성되고
발송은 건너뜁니다(워크플로 실행 아티팩트로 다운로드해서 확인 가능).

## 실행 주기

- `.github/workflows/weekly-briefing.yml`이 매주 월요일 한국시간(KST) 오전 8:00에 자동 실행됩니다.
  (cron은 UTC 기준이라 `0 23 * * 0`, 즉 일요일 UTC 23:00 = 월요일 KST 08:00으로 설정했습니다.)
- 저장소의 **Actions → Weekly News Briefing → Run workflow**에서 언제든 수동 실행할 수 있습니다
  (workflow_dispatch).
- GitHub는 60일간 저장소에 활동이 없으면 공개 저장소의 스케줄을 자동으로 비활성화합니다. 그 경우
  수동 실행 한 번이면 다시 켜집니다.

## 요약 옵션 켜는 법 (기본 꺼짐)

이 프로젝트는 **API 키를 쓰지 않습니다.** 대신 로컬에서 `claude setup-token`으로 만든 Claude Pro/Max
**구독 기반** OAuth 토큰으로 GitHub Actions에서 Claude Code를 실행합니다 (Anthropic 공식 문서 기준으로
지원되는 방식입니다: [Claude Code GitHub Actions](https://code.claude.com/docs/en/github-actions),
[`claude setup-token`](https://code.claude.com/docs/en/authentication#generate-a-long-lived-token)).
이 토큰은 구독 사용량만 소모하고, 1년짜리입니다.

### 1) 요약용 토큰 등록

로컬 PC에서:

```bash
claude setup-token
```

브라우저 로그인 후 출력되는 토큰을 저장소 Secret `CLAUDE_CODE_OAUTH_TOKEN`으로 등록하세요.
(요약 기능을 전혀 쓰지 않을 거라면 이 Secret은 등록하지 않아도 됩니다.)

### 2) 요약 종류 두 가지, 각각 따로 on/off

| 요약 | 내용 | 켜는 방법 |
| --- | --- | --- |
| 일반 기사 요약 | 기사별 한국어 한 줄 요약 | `SUMMARIZE_ARTICLES` |
| Hacker News 쟁점 요약 | 상위 5개 글의 댓글 20~30개를 읽고 "쟁점/주요 반론"을 한국어 3~4줄로 요약 | `SUMMARIZE_HN` |

**수동 실행(workflow_dispatch)**: Actions 탭에서 Run workflow를 누르면 두 옵션을 체크박스로 켤 수 있습니다.

**매주 자동 실행(schedule)**: 저장소 **Settings → Secrets and variables → Actions → Variables** 탭에서
`SUMMARIZE_ARTICLES`, `SUMMARIZE_HN` 값을 각각 `true`로 등록하면 매주 요약이 포함됩니다. 등록하지 않으면
(또는 `false`로 두면) 기본값대로 요약 없이 제목/링크/출처/날짜만 보냅니다.

둘 다 꺼져 있으면 `CLAUDE_CODE_OAUTH_TOKEN`도 전혀 사용되지 않습니다(해당 워크플로 단계 자체가 실행되지 않음).

## 로컬에서 수집만 미리 해보기

```bash
pip install -r requirements.txt
python -m src.collect   # data/articles.json, data/hn.json 생성
python -m src.send      # Secrets(환경변수)가 없으면 자동으로 data/preview.html만 생성
```

Gmail 환경변수를 로컬에서 설정하고 싶다면:

```bash
export GMAIL_USER=me@gmail.com
export GMAIL_APP_PASSWORD=xxxxxxxxxxxxxxxx
export MAIL_TO=me@gmail.com
python -m src.send
```
