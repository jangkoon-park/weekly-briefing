"""feeds.yaml 기반 수집: RSS 분야, Hugging Face Daily Papers, Hacker News."""
import calendar
import logging
import re
import time
from pathlib import Path

import feedparser
import requests
import yaml

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36 daily-weekly-briefing/2.0"
)
REQUEST_TIMEOUT = 20

HF_PAPERS_URL = "https://huggingface.co/api/daily_papers"
ALGOLIA_SEARCH_URL = "https://hn.algolia.com/api/v1/search"


def load_config(path="feeds.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# 키워드 필터
# ---------------------------------------------------------------------------

def compile_keywords(keywords):
    """키워드 목록을 제목 매칭용 정규식으로 바꾼다. 비어 있으면 None(필터 없음).

    - 영문/숫자로만 된 키워드(예: SI, ERP, PostgreSQL)는 대소문자 무시 + 앞뒤가 영문자가 아닐 때만 매칭
      ("SI"가 "ASIA", "SIM" 안에서 걸리지 않도록).
    - 한글 등이 섞인 키워드(예: 기준금리, 공공 클라우드)는 단순 포함 여부로 매칭.
    """
    if not keywords:
        return None
    parts = []
    for kw in keywords:
        kw = str(kw).strip()
        if not kw:
            continue
        escaped = re.escape(kw)
        if re.fullmatch(r"[A-Za-z0-9 .+#\-]+", kw):
            parts.append(rf"(?i:(?<![A-Za-z]){escaped}(?![A-Za-z]))")
        else:
            parts.append(escaped)
    return re.compile("|".join(parts)) if parts else None


def _matches(pattern, text):
    return pattern is None or bool(pattern.search(text or ""))


# ---------------------------------------------------------------------------
# RSS
# ---------------------------------------------------------------------------

def _entry_published_epoch(entry):
    """entry에서 발행 시각(UTC epoch seconds)을 뽑아낸다. 못 찾으면 None."""
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        value = entry.get(key)
        if value:
            return calendar.timegm(value)
    return None


def _get(url, retries=2, **kwargs):
    """GET + 429/5xx면 잠깐 쉬었다가 재시도 (Reddit 등 요청 제한 대응)."""
    for attempt in range(retries + 1):
        response = requests.get(url, timeout=REQUEST_TIMEOUT, **kwargs)
        if response.status_code != 429 and response.status_code < 500:
            return response
        if attempt < retries:
            wait = 10 * (attempt + 1)
            logger.info("  HTTP %d, %d초 후 재시도: %s", response.status_code, wait, url)
            time.sleep(wait)
    return response


def fetch_feed(url, user_agent=None):
    """RSS/Atom 피드를 가져와 feedparser로 파싱한다. 실패하면 예외를 던진다."""
    response = _get(url, headers={"User-Agent": user_agent or USER_AGENT})
    response.raise_for_status()
    parsed = feedparser.parse(response.content)
    if parsed.bozo and not parsed.entries:
        raise ValueError(f"피드를 파싱할 수 없음: {parsed.get('bozo_exception')}")
    return parsed


def _normalize_title(title):
    return re.sub(r"\W+", "", title).lower()


def _round_robin(per_feed_items, limit):
    """피드별 최신순 목록에서 한 개씩 번갈아 뽑아 limit개를 고른 뒤 전체를 최신순으로 정렬한다.

    기사가 많은 피드 하나가 분야 전체를 차지하지 않게 하기 위함.
    """
    queues = [list(items) for items in per_feed_items if items]
    picked = []
    while queues and len(picked) < limit:
        next_round = []
        for queue in queues:
            if len(picked) >= limit:
                break
            picked.append(queue.pop(0))
            if queue:
                next_round.append(queue)
        queues = next_round
    picked.sort(key=lambda x: x["published_epoch"], reverse=True)
    return picked


def collect_rss_category(category, hours_back, max_items, now_epoch):
    cutoff_epoch = now_epoch - hours_back * 3600
    category_pattern = compile_keywords(category.get("keywords"))
    seen_links = set()
    seen_titles = set()
    per_feed_items = []

    for feed_cfg in category.get("feeds", []):
        feed_name = feed_cfg["name"]
        feed_url = feed_cfg["url"]
        # 피드에 keywords가 있으면 분야 keywords 대신 그것을 쓴다.
        pattern = (
            compile_keywords(feed_cfg["keywords"]) if "keywords" in feed_cfg else category_pattern
        )
        try:
            parsed = fetch_feed(feed_url, feed_cfg.get("user_agent"))
        except Exception as exc:  # noqa: BLE001 - 피드 하나 실패해도 전체는 계속 진행
            logger.warning("  [%s] 피드 수집 실패: %s (%s)", feed_name, feed_url, exc)
            continue

        feed_items = []
        in_range = 0
        for entry in parsed.entries:
            link = entry.get("link")
            title = (entry.get("title") or "").strip()
            if not link or not title:
                continue
            published_epoch = _entry_published_epoch(entry)
            if published_epoch is None or published_epoch < cutoff_epoch:
                # 발행일을 모르는 글은 기간 판단이 불가능하므로 제외
                continue
            if published_epoch > now_epoch + 3600:
                # 미래 날짜(예약 글/잘못된 시간대)는 지금 시각으로 간주
                published_epoch = int(now_epoch)
            in_range += 1
            if not _matches(pattern, title):
                continue
            norm = _normalize_title(title)
            if link in seen_links or norm in seen_titles:
                continue
            seen_links.add(link)
            seen_titles.add(norm)
            feed_items.append(
                {
                    "title": title,
                    "link": link,
                    "source": feed_name,
                    "published_epoch": published_epoch,
                }
            )

        feed_items.sort(key=lambda x: x["published_epoch"], reverse=True)
        if feed_cfg.get("max_items"):
            feed_items = feed_items[: int(feed_cfg["max_items"])]
        logger.info(
            "  [%s] 기간 내 %d건, 필터 통과 %d건", feed_name, in_range, len(feed_items)
        )
        per_feed_items.append(feed_items)

    return _round_robin(per_feed_items, max_items)


# ---------------------------------------------------------------------------
# Hugging Face Daily Papers
# ---------------------------------------------------------------------------

def _iso_to_epoch(value):
    return calendar.timegm(time.strptime(value[:19], "%Y-%m-%dT%H:%M:%S"))


def collect_hf_papers(category, hours_back, max_items, now_epoch):
    """HF Daily Papers API에서 기간 내 Daily Papers에 올라온 논문을 추천(upvotes) 많은 순으로 max_items개.

    Daily Papers는 날짜(UTC) 단위 목록이라, 그날의 절반 이상이 기간 안에 들어가는 날짜만 포함한다
    (예: 매일 UTC 23:00 실행이면 '오늘(UTC)' 목록 하나). 날짜마다 API를 한 번씩 부른다.
    """
    cutoff_epoch = now_epoch - hours_back * 3600
    day = int((cutoff_epoch - 43200) // 86400) + 1   # day*86400 + 12h >= cutoff 인 첫 날짜
    last_day = int(now_epoch // 86400)
    seen = set()
    items = []
    while day <= last_day:
        date_str = time.strftime("%Y-%m-%d", time.gmtime(day * 86400))
        day += 1
        try:
            response = _get(
                HF_PAPERS_URL,
                params={"date": date_str, "limit": 100},
                headers={"User-Agent": USER_AGENT},
            )
            if response.status_code in (400, 404):
                # 아직 목록이 만들어지지 않은 날짜
                logger.info("  HF Daily Papers(%s): 목록 없음", date_str)
                continue
            response.raise_for_status()
            data = response.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("  Hugging Face Daily Papers(%s) 수집 실패: %s", date_str, exc)
            continue
        for entry in data:
            paper = entry.get("paper") or {}
            paper_id = paper.get("id")
            title = (entry.get("title") or paper.get("title") or "").strip()
            daily_at = paper.get("submittedOnDailyAt") or entry.get("publishedAt")
            if not paper_id or not title or not daily_at or paper_id in seen:
                continue
            published_epoch = _iso_to_epoch(daily_at)
            seen.add(paper_id)
            upvotes = paper.get("upvotes", 0) or 0
            items.append(
                {
                    "title": " ".join(title.split()),
                    "link": f"https://huggingface.co/papers/{paper_id}",
                    "source": "HF Daily Papers",
                    "published_epoch": published_epoch,
                    "meta": f"추천 {upvotes}",
                    "extra_links": [{"label": "arXiv", "url": f"https://arxiv.org/abs/{paper_id}"}],
                    "_score": upvotes,
                }
            )
    items.sort(key=lambda x: x["_score"], reverse=True)
    logger.info("  HF Daily Papers: 기간 내 %d건", len(items))
    return items[:max_items]


# ---------------------------------------------------------------------------
# Hacker News (Algolia API)
# ---------------------------------------------------------------------------

def collect_hacker_news(category, hours_back, max_items, now_epoch):
    """기간 내 points >= min_points인 글을 포인트 높은 순으로 max_items개."""
    min_points = int(category.get("min_points", 100))
    cutoff_epoch = int(now_epoch - hours_back * 3600)
    params = {
        "tags": "story",
        "numericFilters": f"points>={min_points},created_at_i>={cutoff_epoch}",
        "hitsPerPage": 1000,
    }
    try:
        response = _get(ALGOLIA_SEARCH_URL, params=params)
        response.raise_for_status()
        hits = response.json().get("hits", [])
    except Exception as exc:  # noqa: BLE001
        logger.warning("  Hacker News(Algolia) 수집 실패: %s", exc)
        return []

    hits.sort(key=lambda h: h.get("points", 0) or 0, reverse=True)
    items = []
    for hit in hits:
        object_id = hit.get("objectID")
        title = (hit.get("title") or "").strip()
        if not object_id or not title:
            continue
        hn_link = f"https://news.ycombinator.com/item?id={object_id}"
        items.append(
            {
                "title": title,
                "link": hit.get("url") or hn_link,
                "source": "Hacker News",
                "published_epoch": hit.get("created_at_i") or int(now_epoch),
                "meta": f"▲{hit.get('points', 0)} · 댓글 {hit.get('num_comments', 0) or 0}",
                "extra_links": [{"label": "HN 댓글", "url": hn_link}],
                "hn_id": object_id,
            }
        )
        if len(items) >= max_items:
            break
    logger.info("  Hacker News: %d건 (points>=%d)", len(items), min_points)
    return items


COLLECTORS = {
    "rss": collect_rss_category,
    "hf_papers": collect_hf_papers,
    "hacker_news": collect_hacker_news,
}


def collect_schedule(config, schedule, now_epoch=None):
    """schedule(daily/weekly)에 속한 분야만 수집해서 분야 리스트를 feeds.yaml 순서대로 돌려준다."""
    if now_epoch is None:
        now_epoch = time.time()
    sched_cfg = config["schedules"][schedule]
    hours_back = sched_cfg.get("hours_back", 24)
    default_max = sched_cfg.get("default_max_items", 10)

    results = []
    for category in config.get("categories", []):
        if category.get("schedule") != schedule:
            continue
        ctype = category.get("type", "rss")
        max_items = int(category.get("max_items", default_max))
        logger.info("[%s] %s (type=%s, 최근 %d시간, 최대 %d개)", schedule, category["name"], ctype, hours_back, max_items)
        items = COLLECTORS[ctype](category, hours_back, max_items, now_epoch)
        for item in items:
            item.pop("_score", None)
        results.append({"key": category["key"], "name": category["name"], "type": ctype, "items": items})
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cfg = load_config(Path(__file__).resolve().parent.parent / "feeds.yaml")
    for sched in cfg["schedules"]:
        for cat in collect_schedule(cfg, sched):
            print(sched, cat["name"], len(cat["items"]))
