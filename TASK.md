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
