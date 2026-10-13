"""1단계: feeds.yaml의 8개 분야·34개 섹션을 수집해서 data/briefing.json에 저장.

사용법:
  python -m src.collect                 # 월요일(한국시간)이면 "이번 주 흐름"도 만들도록 표시
  python -m src.collect --trend on      # 요일과 상관없이 이번 주 흐름 포함 (테스트용)
  python -m src.collect --trend off     # 이번 주 흐름 없이
"""
import argparse
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src import history
from src.feeds import collect_all, load_config, new_seen

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
KST = timezone(timedelta(hours=9))


def resolve_trend(flag, now_kst=None):
    """auto → 한국시간 월요일이면 True."""
    if flag in ("on", "true"):
        return True
    if flag in ("off", "false"):
        return False
    now_kst = now_kst or datetime.now(KST)
    return now_kst.weekday() == 0


def _format_item(item):
    published = datetime.fromtimestamp(item["published_epoch"], tz=KST)
    out = {k: v for k, v in item.items() if k != "published_epoch"}
    out["published"] = published.strftime("%Y-%m-%d %H:%M")
    return out


def collect(weekly_trend, config=None, now_kst=None):
    config = config or load_config(ROOT / "feeds.yaml")
    now_kst = now_kst or datetime.now(KST)
    history_days = int(config.get("settings", {}).get("history_days", 35))
    # 최근 발송 기록에 있는 글은 다시 싣지 않는다
    links, keys = history.sent_links_and_keys(now_kst.date(), history_days)
    logger.info("최근 %d일 발송 기록: 링크 %d개", history_days, len(links))
    seen = new_seen(links, keys)  # 메일 한 통 안에서 같은 기사·같은 사건은 한 번만

    groups = collect_all(config, seen=seen)
    return {
        "generated_at": now_kst.isoformat(),
        "date": now_kst.date().isoformat(),
        "weekly_trend": weekly_trend,
        "sections": [
            {
                "key": g["key"],
                "title": g["name"],
                "categories": [{**c, "items": [_format_item(i) for i in c["items"]]} for c in g["categories"]],
            }
            for g in groups
        ],
    }


def log_counts(briefing):
    logger.info("===== 섹션별 건수 (이번 주 흐름: %s) =====", "포함" if briefing["weekly_trend"] else "없음")
    total = 0
    for group in briefing["sections"]:
        for cat in group["categories"]:
            n = len(cat["items"])
            total += n
            kr = sum(1 for i in cat["items"] if i.get("region") == "kr")
            logger.info(
                "  %-6s | %-22s | %d건 (국내 %d·세계 %d)%s",
                group["title"], cat["name"], n, kr, n - kr, "" if n else " → 새 소식 없음",
            )
    logger.info("  합계 %d건", total)
    return total


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trend", choices=("auto", "on", "off"), default="auto")
    args = parser.parse_args()

    weekly_trend = resolve_trend(args.trend)
    DATA_DIR.mkdir(exist_ok=True)
    briefing = collect(weekly_trend)
    log_counts(briefing)

    path = DATA_DIR / "briefing.json"
    path.write_text(json.dumps(briefing, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("저장: %s", path)


if __name__ == "__main__":
    main()
