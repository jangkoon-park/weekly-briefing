"""(선택) Claude 한 번 호출로 처리할 번역·요약 입력을 준비한다.

  python -m src.enrich

환경변수(true/false)로 켜고 끈다:
  TRANSLATE_TITLES    영어 등 한글이 없는 제목을 한국어로 번역 (한국어 제목은 이름뿐일 때만 풀어 쓰기)
  SUMMARIZE_ARTICLES  기사별 쉬운 말 한 줄 요약 (HN 제외, RSS 발췌문 기준)
  SUMMARIZE_HN        HN 글마다 상위 댓글을 참고해 "무슨 일인지" 한 줄 + "찬성 쪽은 ~ / 반대 쪽은 ~" 요약

하는 일:
  1. data/briefing.json의 각 기사에 짧은 id("eid")를 붙여 다시 저장
  2. Claude가 읽을 data/enrich_input.json(필요한 기사만)과 지시문 data/enrich_prompt.md 생성
     - HN 댓글은 여기서 미리 받아 넣어 두므로 Claude는 웹 접속 없이 파일만 읽고 씀
  3. 할 일이 있으면 GITHUB_OUTPUT에 needed=true 기록 → 워크플로가 Claude 단계를 한 번 실행
Claude는 결과를 data/enrich.json({eid: {title_ko, summary, debate}})에 쓰고, src.send가 이를 메일에 반영한다.
"""
import json
import logging
import os
import re
from pathlib import Path

import requests

from src.feeds import USER_AGENT, make_excerpt

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"
ALGOLIA_ITEM_URL = "https://hn.algolia.com/api/v1/items/{}"
HN_TOP_COMMENTS = 20
HN_COMMENT_CHARS = 300
SUMMARY_EXCERPT_CHARS = 300

def _flag(name):
    return os.environ.get(name, "false").strip().lower() == "true"


def fetch_hn_comments(story_id, limit=HN_TOP_COMMENTS):
    """HN 순위 순서(공식 API kids 순서)대로 상위 댓글 텍스트 limit개."""
    try:
        ranked = requests.get(HN_ITEM_URL.format(story_id), timeout=20).json().get("kids", [])
        tree = requests.get(
            ALGOLIA_ITEM_URL.format(story_id), headers={"User-Agent": USER_AGENT}, timeout=30
        ).json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("  HN %s 댓글 수집 실패: %s", story_id, exc)
        return []

    by_id = {}

    def walk(node):
        for child in node.get("children") or []:
            if child.get("text"):
                by_id[child["id"]] = child
            walk(child)

    walk(tree)
    # 상위(최상위) 댓글을 순위대로, 모자라면 그 아래 답글로 채움
    top_ids = [k for k in ranked if k in by_id]
    ordered = [by_id[k] for k in top_ids] + [c for k, c in by_id.items() if k not in set(top_ids)]
    return [make_excerpt(c["text"], HN_COMMENT_CHARS) for c in ordered[:limit]]


PROMPT_HEAD = """# 메일 브리핑 번역·요약 작업

`data/enrich_input.json`을 Read로 읽어라 (파일이 커서 한 번에 안 읽히면 offset/limit로 나눠 끝까지 읽는다).
`items` 배열의 각 원소는 기사 하나이고 `id`가 있다. 모든 원소를 빠짐없이 처리한다.
각 원소에 적힌 `tasks`에 해당하는 작업만 한다. 웹 접속은 하지 말고 파일에 있는 내용만 근거로 쓴다.
읽는 사람은 개발자가 아니다. 휴대폰으로 출근길에 훑어본다고 생각하고 쉬운 말로 쓴다.
"""

TASK_TEXT = {
    "title_ko": """## title_ko — 쉬운 한국어 제목
- 한글이 없는 제목(영어 등): 자연스러운 한국어 기사 제목으로 번역한다. 원문에 없는 내용을 더하지 않는다.
- 한글 제목: 그대로 두고 title_ko를 넣지 않는다. 단, 제목이 제품·회사·프로젝트 이름뿐이라 무슨 내용인지
  안 드러나면 내용이 드러나게 풀어 쓴 제목을 title_ko에 넣는다 (예: "뮤즈 원더" → "뮤즈 원더: 메타가 새로 낸 AI 모델").
- 영어 제목이 이름뿐인 경우도 같은 방식으로 풀어 쓴다 (예: "Show HN: Foo" → "Foo: 개인 개발자가 만든 ○○ 도구").
- 회사·제품·사람 이름은 원어 그대로 두거나 널리 쓰는 한글 표기를 쓴다 (예: OpenAI, PostgreSQL, 구글).
""",
    "summary": """## summary — "무슨 일인지" 쉬운 말 한 줄
- 무슨 일인지 한국어 한 문장(80자 안팎)으로 쓴다.
  - 일반 기사: `title`과 `excerpt`(기사 앞부분 발췌)를 근거로 쓴다.
  - Hacker News 글(`excerpt` 없이 `comments`가 있는 원소): 본문이 없으니 `title`과 댓글 내용을 참고해서
    글이 무엇을 다루는지 설명한다. 댓글 속 의견이 아니라 "무슨 일/무엇인지"를 쓴다.
- 제목이 제품·회사·프로젝트 이름뿐이면 그게 무엇인지 풀어서 쓴다.
  예: "Show HN: Muse Wonder" → "뮤즈 원더: ○○사가 새로 낸 AI 모델".
- 전문용어는 풀어 쓴다. 예: "LLM" → "챗GPT 같은 대형 AI 모델", "레이턴시" → "응답 속도",
  "오픈소스" → "누구나 무료로 쓰고 고칠 수 있게 공개한", "기준금리" → "한국은행이 정하는 기본 금리".
- 발췌문·댓글이 비어 있거나 부족하면 제목에서 알 수 있는 만큼만 쓰고, 추측해서 지어내지 않는다.
  제목·발췌문·댓글로도 무슨 내용인지 알 수 없으면 summary를 딱 "원문 확인 필요"라고만 쓴다.
- `"kind": "essay"`인 원소(에세이·비평·장문 글)는 사건이 아니라 **무슨 주장·내용인지**를 쓴다.
  예: "AI가 인간의 판단을 대신할수록 책임 소재가 흐려진다고 주장하는 에세이".
""",
    "debate": """## debate — HN 댓글 쟁점 (쉬운 말)
- `comments`(Hacker News 상위 댓글)를 읽고 사람들이 무엇을 두고 의견이 갈렸는지 쉬운 한국어로 쓴다.
- 형식은 딱 두 줄: 첫 줄 "찬성 쪽은 ~", 둘째 줄 "반대 쪽은 ~". 각 줄 70자 이내, 줄바꿈은 \\n.
- 뚜렷하게 갈리지 않았으면 한 줄로 "대체로 ~라는 반응" 이라고 쓴다.
- 전문용어는 summary와 같은 방식으로 풀어 쓴다.
""",
}

DUP_TEXT = """## dup_of — 같은 사건 중복 표시
- `items`는 메일에 나오는 순서다. 어떤 원소가 앞에 나온 다른 원소와 **같은 사건**을 다룬다면
  (매체·언어·표현이 달라도) 그 원소에 "dup_of": "<앞 원소의 id>"를 넣는다. 그 원소는 메일에서 빠진다.
- 같은 주제라도 서로 다른 사건(예: 다른 회사의 실적, 다른 날의 발표)이면 표시하지 않는다. 애매하면 표시하지 않는다.

## ad — 광고·보도자료성 기사 표시
- 기사가 특정 상품·서비스·업체 홍보가 목적인 광고성 글이거나, 기업 보도자료를 그대로 옮긴 홍보성 글이면
  "ad": true를 넣는다 (예: 건강식품·영양제 홍보, 할인·이벤트 안내, 신제품 홍보 일색, 행사 개최 알림). 그 원소는 메일에서 빠진다.
- 기업 소식이라도 실적·투자·사고·정책처럼 뉴스 가치가 있으면 표시하지 않는다. 애매하면 표시하지 않는다.
"""

PROMPT_TAIL = """## 결과 저장
결과를 `data/enrich.json`에 Write로 저장한다. 구조:
{ "<id>": { "title_ko": "...", "summary": "...", "debate": "...", "dup_of": "...", "ad": true }, ... }
- 각 id에는 그 원소의 `tasks`에 있는 키와 (해당할 때만) dup_of·ad만 넣는다. 넣을 게 없는 id는 빼도 된다.
- 반드시 유효한 JSON만 저장한다. 마크다운 코드블록이나 설명을 붙이지 않는다.
- 원소가 많아 한 번에 쓰기 길면 같은 구조로 `data/enrich_out_1.json`, `data/enrich_out_2.json` … 처럼
  여러 파일로 나눠 저장해도 된다 (id가 겹치지 않게). 이 파일들 외에는 만들거나 고치지 않는다.
"""


def prepare(translate, summarize, summarize_hn):
    briefing_path = DATA_DIR / "briefing.json"
    briefing = json.loads(briefing_path.read_text(encoding="utf-8"))

    inputs = []
    counter = 0
    used_tasks = set()
    for section in briefing["sections"]:
        for cat in section["categories"]:
            is_hn = cat.get("type") == "hacker_news"
            is_essay = cat.get("summary_style") == "essay"
            for item in cat["items"]:
                counter += 1
                item["eid"] = f"i{counter}"
                tasks = []
                if translate:
                    # 영어 제목은 번역, 한글 제목은 이름뿐일 때만 풀어 쓰기 (판단은 Claude가)
                    tasks.append("title_ko")
                if summarize and not is_hn:
                    tasks.append("summary")
                entry = {"id": item["eid"], "title": item["title"]}
                if summarize_hn and is_hn:
                    # HN은 본문이 없으므로 상위 댓글을 근거로 "무슨 일인지" 설명 + 찬반 쟁점
                    tasks.append("summary")
                    comments = fetch_hn_comments(item["hn_id"]) if item.get("hn_id") else []
                    if comments:
                        tasks.append("debate")
                        entry["comments"] = comments
                if not tasks:
                    continue
                if "summary" in tasks and not is_hn:
                    entry["excerpt"] = make_excerpt(item.get("excerpt", ""), SUMMARY_EXCERPT_CHARS)
                if is_essay:
                    entry["kind"] = "essay"
                entry["tasks"] = tasks
                used_tasks.update(tasks)
                inputs.append(entry)

    briefing_path.write_text(json.dumps(briefing, ensure_ascii=False, indent=2), encoding="utf-8")

    if not inputs:
        logger.info("번역·요약할 항목이 없습니다 (옵션이 모두 꺼져 있거나 대상 기사 없음).")
        return False

    (DATA_DIR / "enrich_input.json").write_text(
        json.dumps({"items": inputs}, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    prompt = PROMPT_HEAD + "".join(TASK_TEXT[t] for t in ("title_ko", "summary", "debate") if t in used_tasks)
    prompt += DUP_TEXT
    (DATA_DIR / "enrich_prompt.md").write_text(prompt + PROMPT_TAIL, encoding="utf-8")
    counts = {t: sum(t in e["tasks"] for e in inputs) for t in sorted(used_tasks)}
    logger.info("Claude 입력 준비: 기사 %d건, 작업 %s", len(inputs), counts)
    return True


def main():
    translate = _flag("TRANSLATE_TITLES")
    summarize = _flag("SUMMARIZE_ARTICLES")
    summarize_hn = _flag("SUMMARIZE_HN")
    logger.info(
        "TRANSLATE_TITLES=%s SUMMARIZE_ARTICLES=%s SUMMARIZE_HN=%s", translate, summarize, summarize_hn
    )
    needed = prepare(translate, summarize, summarize_hn)
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as f:
            f.write(f"needed={'true' if needed else 'false'}\n")


if __name__ == "__main__":
    main()
