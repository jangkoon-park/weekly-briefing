"""발송한 기사 누적 저장 (data/history/YYYY-MM-DD.json)과 주간 흐름 저장 (data/trends/YYYY-MM-DD.json).

- history: 매일 메일에 실제로 실린 기사(번역 제목·한 줄 설명 포함). 최근 N일(기본 35일 = 5주)만 남긴다.
  1) 다음 날부터 같은 글이 다시 실리지 않게 하는 데 쓰고 (feeds.select_items)
  2) 월요일 "이번 주 흐름"을 만들 때 지난 7일치 재료로 쓴다 (enrich).
- trends: 월요일마다 만든 "이번 주 흐름". 다음 주에 🆕/➡️/🔻(지난주 대비)를 판단할 때 쓴다.

GitHub Actions에서는 발송 후 이 두 폴더를 저장소에 커밋해서 다음 실행으로 이어진다.
"""
import json
import logging
from datetime import date, timedelta
from pathlib import Path

from src.feeds import title_key

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
HISTORY_DIR = ROOT / "data" / "history"
TRENDS_DIR = ROOT / "data" / "trends"


def _read(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as exc:
        logger.warning("%s 읽기 실패: %s", path, exc)
        return None


def recent_days(today, days):
    """today 이전(today 제외) days일 안의 history 파일 내용을 오래된 순으로."""
    result = []
    if not HISTORY_DIR.exists():
        return result
    start = today - timedelta(days=days)
    for path in sorted(HISTORY_DIR.glob("*.json")):
        try:
            day = date.fromisoformat(path.stem)
        except ValueError:
            continue
        if start <= day < today:
            data = _read(path)
            if data:
                result.append(data)
    return result


def sent_links_and_keys(today, days):
    links, keys = set(), set()
    for day in recent_days(today, days):
        for item in day.get("items", []):
            links.add(item.get("link"))
            keys.add(title_key(item.get("title", "")))
    links.discard(None)
    keys.discard("")
    return links, keys


def save_day(today, briefing, enrich):
    """오늘 메일에 실린 기사를 data/history/<today>.json으로 저장한다."""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    items = []
    for group in briefing["sections"]:
        for cat in group["categories"]:
            for item in cat["items"]:
                extra = enrich.get(item.get("eid")) if item.get("eid") else None
                extra = extra if isinstance(extra, dict) else {}
                items.append(
                    {
                        "group": group["key"],
                        "section": cat["key"],
                        "region": item.get("region"),
                        "title": item["title"],
                        "title_ko": extra.get("title_ko"),
                        "summary": extra.get("summary"),
                        "link": item["link"],
                        "source": item.get("source"),
                        "published": item.get("published"),
                    }
                )
    path = HISTORY_DIR / f"{today.isoformat()}.json"
    path.write_text(json.dumps({"date": today.isoformat(), "items": items}, ensure_ascii=False, indent=1), encoding="utf-8")
    logger.info("발송 기록 저장: %s (%d건)", path, len(items))
    return path


def prune(today, days):
    """days일보다 오래된 history는 지운다 (trends는 지난주 비교용으로 같은 기간만 남김)."""
    removed = 0
    for folder in (HISTORY_DIR, TRENDS_DIR):
        if not folder.exists():
            continue
        for path in folder.glob("*.json"):
            try:
                day = date.fromisoformat(path.stem)
            except ValueError:
                continue
            if day < today - timedelta(days=days):
                path.unlink()
                removed += 1
    if removed:
        logger.info("오래된 기록 %d개 삭제 (%d일 초과)", removed, days)


def previous_trend_path(today):
    """today보다 앞선 가장 최근의 trends 파일 경로 (없으면 None)."""
    if not TRENDS_DIR.exists():
        return None
    candidates = []
    for path in TRENDS_DIR.glob("*.json"):
        try:
            day = date.fromisoformat(path.stem)
        except ValueError:
            continue
        if day < today:
            candidates.append((day, path))
    return max(candidates)[1] if candidates else None


def save_trend(today, trend):
    TRENDS_DIR.mkdir(parents=True, exist_ok=True)
    path = TRENDS_DIR / f"{today.isoformat()}.json"
    path.write_text(json.dumps(trend, ensure_ascii=False, indent=1), encoding="utf-8")
    logger.info("이번 주 흐름 저장: %s", path)
    return path
