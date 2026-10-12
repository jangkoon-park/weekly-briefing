"""feeds.yaml 기반 RSS 수집."""
import calendar
import logging
from pathlib import Path

import feedparser
import requests
import yaml

logger = logging.getLogger(__name__)

USER_AGENT = "weekly-news-briefing/1.0 (+https://github.com/)"
REQUEST_TIMEOUT = 15


def load_config(path="feeds.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _entry_published_epoch(entry):
    """entry에서 발행 시각(UTC epoch seconds)을 뽑아낸다. 못 찾으면 None."""
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        value = entry.get(key)
        if value:
            return calendar.timegm(value)
    return None


def fetch_feed(url):
    """RSS/Atom 피드를 가져와 feedparser로 파싱한다. 실패하면 예외를 던진다."""
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    parsed = feedparser.parse(response.content)
    if parsed.bozo and not parsed.entries:
        raise ValueError(f"피드를 파싱할 수 없음: {parsed.get('bozo_exception')}")
    return parsed


def collect_category(category, days_back, max_items, now_epoch):
    """하나의 분야(category dict: key/name/feeds)에 대해 최근 N일, 중복 제거, 최대 M개로 수집."""
    cutoff_epoch = now_epoch - days_back * 86400
    seen_links = set()
    items = []

    for feed_cfg in category.get("feeds", []):
        feed_name = feed_cfg["name"]
        feed_url = feed_cfg["url"]
        try:
            parsed = fetch_feed(feed_url)
        except Exception as exc:  # noqa: BLE001 - 피드 하나 실패해도 전체는 계속 진행
            logger.warning("[%s] 피드 수집 실패: %s (%s)", feed_name, feed_url, exc)
            continue

        count_in_range = 0
        for entry in parsed.entries:
            link = entry.get("link")
            title = entry.get("title")
            if not link or not title:
                continue

            published_epoch = _entry_published_epoch(entry)
            if published_epoch is None:
                # 발행일을 알 수 없는 기사는 "최근 7일" 여부를 판단할 수 없으므로 제외한다.
                continue
            if published_epoch < cutoff_epoch:
                continue
            if link in seen_links:
                continue

            seen_links.add(link)
            count_in_range += 1
            items.append(
                {
                    "title": title.strip(),
                    "link": link,
                    "source": feed_name,
                    "published_epoch": published_epoch,
                }
            )

        logger.info("[%s] 최근 %d일 내 기사 %d건 수집", feed_name, days_back, count_in_range)

    items.sort(key=lambda x: x["published_epoch"], reverse=True)
    return items[:max_items]


def collect_all(config, now_epoch=None):
    """feeds.yaml 전체 설정을 받아 분야별 수집 결과 리스트를 돌려준다."""
    import time

    if now_epoch is None:
        now_epoch = time.time()

    settings = config.get("settings", {})
    days_back = settings.get("days_back", 7)
    max_items = settings.get("max_items_per_category", 10)

    results = []
    for category in config.get("categories", []):
        items = collect_category(category, days_back, max_items, now_epoch)
        results.append(
            {
                "key": category["key"],
                "name": category["name"],
                "items": items,
            }
        )
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cfg = load_config(Path(__file__).resolve().parent.parent / "feeds.yaml")
    for cat in collect_all(cfg):
        print(cat["name"], len(cat["items"]))
