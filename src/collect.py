"""1단계: feeds.yaml에 따라 데일리/주간 분야를 수집해서 data/briefing.json에 저장.

사용법:
  python -m src.collect --mode auto     # 한국시간 월요일이면 both, 그 외 daily (예약 실행 기본값)
  python -m src.collect --mode daily
  python -m src.collect --mode weekly
  python -m src.collect --mode both
"""
import argparse
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.feeds import collect_schedule, load_config

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
KST = timezone(timedelta(hours=9))

MODES = ("auto", "daily", "weekly", "both")


def resolve_mode(mode, now_kst=None):
    """auto → 한국시간 월요일이면 both, 아니면 daily."""
    if mode != "auto":
        return mode
    now_kst = now_kst or datetime.now(KST)
    return "both" if now_kst.weekday() == 0 else "daily"


def schedules_for(mode):
    return {"daily": ["daily"], "weekly": ["weekly"], "both": ["daily", "weekly"]}[mode]


def _format_item(item):
    published = datetime.fromtimestamp(item["published_epoch"], tz=KST)
    out = {k: v for k, v in item.items() if k != "published_epoch"}
    out["published"] = published.strftime("%Y-%m-%d %H:%M")
    return out


def collect(mode, config=None):
    config = config or load_config(ROOT / "feeds.yaml")
    sections = []
    for schedule in schedules_for(mode):
        categories = collect_schedule(config, schedule)
        sections.append(
            {
                "schedule": schedule,
                "title": config["schedules"][schedule].get("title", schedule),
                "categories": [
                    {**cat, "items": [_format_item(i) for i in cat["items"]]} for cat in categories
                ],
            }
        )
    return {
        "generated_at": datetime.now(KST).isoformat(),
        "mode": mode,
        "sections": sections,
    }


def log_counts(briefing):
    logger.info("===== 분야별 건수 (mode=%s) =====", briefing["mode"])
    total = 0
    for section in briefing["sections"]:
        for cat in section["categories"]:
            n = len(cat["items"])
            total += n
            logger.info("  %-6s | %-24s | %2d건%s", section["schedule"], cat["name"], n, "" if n else " (메일에서 생략)")
    logger.info("  합계 %d건", total)
    return total


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=MODES, default="auto")
    args = parser.parse_args()

    mode = resolve_mode(args.mode)
    logger.info("실행 모드: %s (요청: %s)", mode, args.mode)

    DATA_DIR.mkdir(exist_ok=True)
    briefing = collect(mode)
    log_counts(briefing)

    path = DATA_DIR / "briefing.json"
    path.write_text(json.dumps(briefing, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("저장: %s", path)


if __name__ == "__main__":
    main()
