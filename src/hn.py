"""Hacker News 수집 (Algolia HN Search API 사용, 크롤링 없음)."""
import logging
import time

import requests

logger = logging.getLogger(__name__)

ALGOLIA_SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date"
REQUEST_TIMEOUT = 15


def collect_hacker_news(min_points=200, days_back=7, max_items=5, now_epoch=None):
    """최근 days_back일 중 points >= min_points인 글 상위 max_items개를 points 내림차순으로 반환."""
    if now_epoch is None:
        now_epoch = time.time()
    cutoff_epoch = int(now_epoch - days_back * 86400)

    params = {
        "tags": "story",
        "numericFilters": f"points>={min_points},created_at_i>={cutoff_epoch}",
        "hitsPerPage": 100,
    }

    try:
        response = requests.get(ALGOLIA_SEARCH_URL, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Hacker News(Algolia) 수집 실패: %s", exc)
        return []

    hits = data.get("hits", [])
    hits.sort(key=lambda h: h.get("points", 0), reverse=True)

    items = []
    for hit in hits[:max_items]:
        object_id = hit.get("objectID")
        title = hit.get("title")
        if not object_id or not title:
            continue
        article_url = hit.get("url") or f"https://news.ycombinator.com/item?id={object_id}"
        items.append(
            {
                "id": object_id,
                "title": title.strip(),
                "url": article_url,
                "hn_link": f"https://news.ycombinator.com/item?id={object_id}",
                "points": hit.get("points", 0),
                "num_comments": hit.get("num_comments", 0),
            }
        )

    logger.info("Hacker News: %d건 수집 (points>=%d, 최근 %d일)", len(items), min_points, days_back)
    return items


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for item in collect_hacker_news():
        print(item["points"], item["title"], item["url"])
