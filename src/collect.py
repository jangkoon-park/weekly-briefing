"""1단계: RSS + Hacker News 수집해서 data/articles.json, data/hn.json에 저장."""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.feeds import collect_all, load_config
from src.hn import collect_hacker_news

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"


def _format_item(item):
    published = datetime.fromtimestamp(item["published_epoch"], tz=timezone.utc)
    return {
        "title": item["title"],
        "link": item["link"],
        "source": item["source"],
        "published": published.strftime("%Y-%m-%d"),
    }


def main():
    DATA_DIR.mkdir(exist_ok=True)

    config = load_config(ROOT / "feeds.yaml")
    categories = collect_all(config)

    articles_out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "categories": [
            {
                "key": cat["key"],
                "name": cat["name"],
                "items": [_format_item(i) for i in cat["items"]],
            }
            for cat in categories
        ],
    }
    articles_path = DATA_DIR / "articles.json"
    articles_path.write_text(
        json.dumps(articles_out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    total = sum(len(c["items"]) for c in articles_out["categories"])
    logger.info("articles.json 저장: 분야 %d개, 기사 %d건 -> %s", len(categories), total, articles_path)

    hn_cfg = config.get("hacker_news", {})
    hn_items = collect_hacker_news(
        min_points=hn_cfg.get("min_points", 200),
        days_back=hn_cfg.get("days_back", 7),
        max_items=hn_cfg.get("max_items", 5),
    )
    hn_out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": hn_items,
    }
    hn_path = DATA_DIR / "hn.json"
    hn_path.write_text(json.dumps(hn_out, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("hn.json 저장: %d건 -> %s", len(hn_items), hn_path)


if __name__ == "__main__":
    main()
