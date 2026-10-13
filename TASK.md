# 주간 뉴스 브리핑 자동화

## 목적
- 매주 관심 분야 뉴스의 제목과 링크를 모아 내 지메일로 보낸다
- 기본은 AI 요약 없이 제목 + 링크 + 출처 + 날짜만

## 수집
- Python + feedparser로 RSS 수집
- 피드 목록과 분야는 feeds.yaml에 따로 분리해서 내가 쉽게 추가/삭제할 수 있게
- 분야 3개로 시작:
  1) AI·데이터 도구 (LLM, Claude, 데이터 엔지니어링)
  2) 프리랜서·업워크 시장
  3) 건설 IT·ERP
- 아래 사이트는 반드시 포함 (RSS 주소는 직접 찾아서 실제로 동작하는지 확인):
  AI·데이터: GeekNews(news.hada.io), Anthropic 공지(anthropic.com/news)
  프리랜서: Upwork 블로그
- 그 외에도 각 분야에 맞는 영어·한국어 RSS를 적당히 골라 추가해줘 (공식 RSS만, 사이트 직접 크롤링 금지)
- RSS가 없는 사이트는 억지로 크롤링하지 말고, 없다고 알려줘
- 최근 7일 기사만, 중복 링크 제거, 분야별 최대 10개

## Hacker News (별도 섹션)
- Hacker News 공식 API 또는 Algolia HN API 사용 (크롤링 금지)
- 최근 7일 중 포인트 높은 글 상위 5개 (200점 이상)
- 각 글마다 기사 링크와 HN 댓글 페이지 링크를 함께 표시

## 발송
- 지메일 SMTP + 앱 비밀번호
- 계정 정보는 코드에 쓰지 말고 환경변수로: GMAIL_USER, GMAIL_APP_PASSWORD, MAIL_TO
- 메일은 HTML로 분야별 섹션 구분, 휴대폰에서 읽기 편하게

## 실행
- GitHub Actions 워크플로 추가
- 매주 월요일 한국시간 오전 8시 실행 (cron은 UTC 기준으로 변환)
- workflow_dispatch로 수동 실행 버튼도 추가
- 위 3개 값은 Actions Secrets에서 읽기

## 요약 옵션 (기본 꺼짐)
- API 키는 절대 쓰지 말 것 (별도 과금이라 안 씀)
- 내 Claude Pro 구독 토큰(claude setup-token)으로 GitHub Actions에서 Claude Code를 실행하는 방식이 가능한지 공식 문서 기준으로 확인
- 가능하면 두 가지 요약을 옵션으로 넣고 기본은 꺼둘 것:
  1) 일반 기사: 기사별 한 줄 요약
  2) Hacker News: 상위 5개 글마다 상위 댓글 20~30개를 읽고 "어떤 쟁점으로 갈렸는지, 주요 반론은 뭔지" 3~4줄 한국어 요약
- 두 요약은 각각 따로 켜고 끌 수 있게
- 불가능하면 이유만 알려줘

## 마무리
- requirements.txt, README에 설정 방법(Secrets 등록, 피드 추가 방법, 요약 켜는 법) 정리
- 실제 메일 발송은 Secrets가 없으니 테스트하지 말고, 수집 부분은 실행해서 동작 확인해줘
- 작업 끝나면 브랜치에 push하고 무엇을 만들었는지, feeds.yaml에 어떤 사이트가 들어갔는지 알려줘

- 이 지시 내용 전체를 저장소에 TASK.md로 저장해서 같이 push해줘

---

# 2차 변경: 데일리 + 주간 두 가지로 분리

기존 발송 방식(지메일 SMTP, Secrets 3개 `GMAIL_USER` / `GMAIL_APP_PASSWORD` / `MAIL_TO`)은 그대로 유지.

## 실행 일정
- 데일리: 매일 한국시간 오전 8시 (cron은 UTC로 변환), 최근 24시간 기사
- 주간: 매주 월요일 한국시간 오전 8시, 최근 7일 기사
- 월요일에는 두 개를 따로 보내지 말고 한 통으로 합쳐서 발송 (위에 데일리, 아래에 주간)
- 메일 제목: 평일은 "[데일리 브리핑] YYYY-MM-DD", 월요일은 "[데일리+주간 브리핑] YYYY-MM-DD"
- workflow_dispatch 수동 실행에서 daily / weekly / both 중 고를 수 있게

## 데일리 분야 (메일에 이 순서로 표시, 분야별 최대 5개)
1) AI·데이터 도구 (기존 유지) + 추가: Simon Willison 블로그, Hugging Face 블로그, OpenAI 뉴스, Google DeepMind 블로그, AI타임스(국내)
2) ML 논문: Hugging Face Daily Papers — 추천 많은 상위 3개
3) 국내 경제·제도: 연합뉴스·한국경제 등 경제 섹션 RSS
   - 제목에 다음 키워드가 있는 기사만: 금리, 기준금리, 환율, 코스피, 경기, 물가, 부동산, 전세, 재건축, 세법, 상속, 증여, 종합소득세, 프리랜서
4) 국내 IT 정책·업계: 전자신문, 지디넷코리아, 블로터, 바이라인네트워크 등 IT RSS
   - 제목에 다음 키워드가 있는 기사만: 공공 클라우드, 망분리, 클라우드 네이티브, AI 사업, 생성형 AI, 차세대, SI, 오라클, PostgreSQL, ERP, 데이터센터, 네이버, 카카오
5) Hacker News: 최근 24시간 포인트 상위 5개 (100점 이상), 기사 링크 + 댓글 링크

## 주간 분야 (메일에 이 순서로 표시, 따로 적지 않으면 분야별 최대 10개)
1) DB·데이터 엔지니어링: Planet PostgreSQL, SQLBI, Power BI 공식 블로그, Oracle Database Insider 블로그, Data Engineering Weekly, 우아한형제들·토스·카카오 기술블로그
2) 프리랜서·업워크 시장 (기존 유지) + 추가: Upwork Research Institute, Reddit r/Upwork(주간 상위 글만)
3) 과학·수학: Quanta Magazine
4) 생각·인문: Astral Codex Ten, Aeon, Psyche, Noema Magazine, LessWrong(큐레이티드 피드만)
5) 책·서평: Five Books, 채널예스
6) 미술
   - 해외: Colossal, Hyperallergic(최대 5개), e-flux Journal(전시 공지 피드 말고 저널만), Artforum, Frieze
   - 국내: 국립현대미술관(MMCA) 전시·소식, 아트인컬처, 월간미술 등 국내 미술 매체 중 RSS 있는 곳
7) 건축·공간: Dezeen, ArchDaily — 설치·전시·공간 연출 관련 글 위주, 최대 5개

## 삭제
- 기존 "건설 IT·ERP" 분야와 그 피드는 제거

## 공통 규칙
- feeds.yaml에서 분야마다 daily / weekly를 지정할 수 있게 해서, 나중에 분야를 옮길 수 있게
- RSS 주소는 직접 찾아서 실제로 동작하는지 확인
- RSS가 없거나 최근 3개월간 글이 없는 사이트는 넣지 말고 목록으로 알려줘 (Edge.org, Ribbonfarm도 확인만 해서 같이 알려줘)
- 키워드 필터와 분야별 최대 개수는 feeds.yaml에서 수정할 수 있게
- 해당 기간에 글이 없는 분야는 섹션째 생략, 전 분야가 비면 메일 안 보냄

## 메일 형식
- 맨 위에 목차: 분야명 + 건수, 누르면 해당 섹션으로 이동
- 지메일 102KB 잘림을 피하도록 HTML은 가볍게, 이미지 없이
- 생성된 HTML 크기를 로그에 출력하고, 100KB를 넘으면 분야별 개수를 자동으로 줄여서 맞춤

## 예약 실행 유지
- 공개 저장소는 60일간 커밋이 없으면 예약 실행이 꺼지므로, 매월 1일 last_run.txt에 날짜를 기록해 커밋하는 keepalive 워크플로 추가 (permissions: contents: write)

## 마무리
- TASK.md에 이번 변경 내용 반영, README에 데일리/주간 구조와 분야 옮기는 법 정리
- 수집 부분만 daily, weekly 각각 실행해서 분야별 건수와 메일 HTML 크기 확인
- 브랜치에 push하고 최종 feeds.yaml 사이트 목록과 제외된 사이트를 알려줘
