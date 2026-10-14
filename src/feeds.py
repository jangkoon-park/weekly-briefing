"""feeds.yaml 기반 수집: RSS 분야, Hugging Face Daily Papers, Hacker News."""
import calendar
import html
import logging
import re
import time
from pathlib import Path
from urllib.parse import urlparse

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


# 요청 제한이 빡빡한 호스트는 요청 사이 간격을 둔다 (초)
HOST_MIN_INTERVAL = {"www.reddit.com": 15}
_last_request = {}


def _wait_for_host(url):
    host = urlparse(url).netloc
    interval = HOST_MIN_INTERVAL.get(host)
    if interval:
        elapsed = time.time() - _last_request.get(host, 0)
        if elapsed < interval:
            time.sleep(interval - elapsed)
        _last_request[host] = time.time()


def _get(url, retries=2, **kwargs):
    """GET + 429/5xx면 잠깐 쉬었다가 재시도 (Reddit 등 요청 제한 대응)."""
    for attempt in range(retries + 1):
        _wait_for_host(url)
        response = requests.get(url, timeout=REQUEST_TIMEOUT, **kwargs)
        if response.status_code != 429 and response.status_code < 500:
            return response
        if attempt < retries:
            wait = 15 * (attempt + 1)
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


EXCERPT_CHARS = 500


def make_excerpt(text, limit=EXCERPT_CHARS):
    """HTML 태그를 지우고 공백을 정리해 limit자 이내로 자른 발췌문 (요약용 입력)."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = " ".join(html.unescape(text).split())
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


def _normalize_title(title):
    return re.sub(r"\W+", "", title).lower()


def _round_robin(per_feed_items):
    """피드별 최신순 목록에서 한 개씩 번갈아 꺼낸 순서 (한 피드가 분야를 독차지하지 않게)."""
    queues = [list(items) for items in per_feed_items if items]
    ordered = []
    while queues:
        next_round = []
        for queue in queues:
            ordered.append(queue.pop(0))
            if queue:
                next_round.append(queue)
        queues = next_round
    return ordered


# ---------------------------------------------------------------------------
# 같은 사건 판별 (제목 유사도)
# ---------------------------------------------------------------------------

DEFAULT_SIMILARITY = 0.5


def title_key(title):
    """[속보]·(종합) 같은 꼬리표를 지우고 소문자 단어 목록으로 만든 비교용 제목 (공백으로 이어 붙인 문자열)."""
    title = re.sub(r"\[[^\]]*\]|\([^)]*\)|【[^】]*】|<[^>]*>", " ", title)
    return " ".join(re.findall(r"[0-9a-z가-힣]+", title.lower()))


def _bigrams(key):
    key = key.replace(" ", "")
    return {key[i:i + 2] for i in range(len(key) - 1)} or {key}


# 같은 주어로 시작하는 서로 다른 기사에도 흔히 나오는 말 (공통 단어로 치지 않음)
GENERIC_WORDS = set("""
대통령 정부 장관 국회 여당 야당 발표 개최 실적 사업 추진 확대 강화 국내 최초 글로벌 종합 속보 단독 출시 공개 선정
기업 시장 서비스 기술 관련 지원 협력 체결 위해 대한 올해 내년 오늘 이번 지난 신규 사상 최대 최고 전년 대비 영업이익
매출 분기 예정 계획 가능 논란 의혹 입장 결정 확인 진행 참석 주재 회의 행사 업계 산업 정책 투자 협약 기념 성료 마무리
the a an and or of to in on for with by at from as is are was were be its his her their this that these those
how why what who when new first more than after over into about says said will can could may not no
""".split())


def _salient_words(words):
    return [w for w in words if len(w) >= 2 and not w.isdigit() and w not in GENERIC_WORDS]


def _shared_count(words_a, words_b):
    """조사·복수형 차이는 무시하고(앞부분 일치) 함께 쓰인 단어 수."""
    count = 0
    for wa in set(words_a):
        if any((wa.startswith(wb) or wb.startswith(wa)) and min(len(wa), len(wb)) >= 2 for wb in set(words_b)):
            count += 1
    return count


def is_same_story(key_a, key_b, threshold=DEFAULT_SIMILARITY):
    """두 제목(title_key 결과)이 같은 사건인지 대략 판별한다.

    1) (한글 제목) 첫 단어(대개 주어)가 같고, 흔한 말이 아닌 단어를 하나 이상 함께 쓰면 같은 사건
       ("코스피 6%대 급락…" / "코스피 장중 4%대 급락…", "삼성SDS 우정항공 인수" / "삼성SDS가 우정항공 택한 이유")
    2) 주어가 달라도 흔하지 않은 단어를 여러 개 함께 쓰고 글자도 꽤 겹치면 같은 사건 (영어는 더 엄격)
    3) 아니면 글자 2-gram 겹침(Dice 계수)이 threshold 이상일 때. 단, 첫 단어가 다르면
       ("삼성전자 3분기 실적" / "LG전자 3분기 실적") 거의 똑같은 제목(0.85 이상)만.
    표현이 많이 다르거나 언어가 다른 중복은 Claude 단계(dup_of)에서 한 번 더 걸러낸다.
    """
    if not key_a or not key_b:
        return False
    if key_a == key_b:
        return True
    words_a, words_b = key_a.split(" "), key_b.split(" ")
    first_a, first_b = words_a[0], words_b[0]
    same_subject = (first_a.startswith(first_b) or first_b.startswith(first_a)) and min(
        len(first_a), len(first_b)
    ) >= 2 and first_a not in GENERIC_WORDS
    # 영어 제목은 큰 고유명사(NASA, Trump, Russia…)가 여러 기사에 겹쳐 나오므로 단어 규칙을 쓰지 않고
    # 글자 겹침만 보수적으로 본다. 표현이 다른 영어 중복은 Claude 단계(dup_of)가 거른다.
    korean = bool(re.search(r"[가-힣]", key_a)) and bool(re.search(r"[가-힣]", key_b))
    if same_subject and korean:
        # 주어가 여러 단어("LG CNS")일 수 있으니 앞에서부터 같은 단어는 모두 떼고 나머지끼리 비교
        n = 1
        while n < min(len(words_a), len(words_b)) and words_a[n] == words_b[n]:
            n += 1
        if _shared_count(_salient_words(words_a[n:]), _salient_words(words_b[n:])) >= 1:
            return True
    a, b = _bigrams(key_a), _bigrams(key_b)
    dice = 2 * len(a & b) / (len(a) + len(b))
    # 주어가 달라도 흔하지 않은 단어를 여러 개 함께 쓰면 같은 사건
    # ("토탈미술관 50주년 특별전…" / "개관 50주년 토탈미술관 특별전…")
    shared = _shared_count(_salient_words(words_a), _salient_words(words_b))
    if korean and ((shared >= 3 and dice >= 0.3) or (shared >= 2 and dice >= 0.4)):
        return True
    if not korean and shared >= 3 and dice >= 0.5:
        return True
    return dice >= (threshold if same_subject else max(threshold, 0.85))


def _rank_by_coverage(per_feed_items, threshold):
    """여러 매체가 함께 다룬 사건일수록 앞에 오도록 묶어서 정렬한다.

    같은 사건 묶음에서는 feeds.yaml에서 먼저 적힌 피드의 기사를 대표로 쓰고, "N개 매체 보도"를 붙인다.
    """
    clusters = []  # [{"items": [...], "keys": [...]}]
    for feed_items in per_feed_items:          # 피드 순서 = 우선순위
        for item in feed_items:
            key = title_key(item["title"])
            for cluster in clusters:
                if any(is_same_story(key, k, threshold) for k in cluster["keys"]):
                    cluster["items"].append(item)
                    cluster["keys"].append(key)
                    break
            else:
                clusters.append({"items": [item], "keys": [key]})

    ranked = []
    for cluster in clusters:
        rep = dict(cluster["items"][0])
        sources = {i["source"] for i in cluster["items"]}
        rep["_coverage"] = len(sources)
        rep["_latest"] = max(i["published_epoch"] for i in cluster["items"])
        if len(sources) >= 2:
            rep["meta"] = f"{len(sources)}개 매체 보도"
        ranked.append(rep)
    ranked.sort(key=lambda x: (x["_coverage"], x["_latest"]), reverse=True)
    for rep in ranked:
        rep.pop("_coverage")
        rep.pop("_latest")
    return ranked


def collect_rss_category(category, hours_back, now_epoch):
    """분야의 후보 기사 목록(우선순위 순)을 돌려준다. 개수 제한·분야 간 중복 제거는 select_items에서."""
    category_pattern = compile_keywords(category.get("keywords"))
    category_exclude = compile_keywords(category.get("exclude_keywords"))
    # settings.exclude_keywords (광고·보도자료성 등) 는 모든 RSS 분야에 항상 적용
    global_exclude = compile_keywords(category.get("_global_exclude"))
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
        exclude = (
            compile_keywords(feed_cfg["exclude_keywords"])
            if "exclude_keywords" in feed_cfg
            else category_exclude
        )
        # 격주간지처럼 글이 드문 피드는 feeds.yaml에서 hours_back을 따로 줄 수 있다
        cutoff_epoch = now_epoch - float(feed_cfg.get("hours_back", hours_back)) * 3600
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
            if exclude is not None and exclude.search(title):
                continue
            if global_exclude is not None and global_exclude.search(title):
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
                    "region": feed_region(feed_cfg),
                    "published_epoch": published_epoch,
                    "excerpt": make_excerpt(entry.get("summary") or entry.get("description")),
                }
            )

        feed_items.sort(key=lambda x: x["published_epoch"], reverse=True)
        if feed_cfg.get("max_items"):
            feed_items = feed_items[: int(feed_cfg["max_items"])]
        logger.info(
            "  [%s] 기간 내 %d건, 필터 통과 %d건", feed_name, in_range, len(feed_items)
        )
        per_feed_items.append(feed_items)

    if category.get("rank") == "coverage":
        threshold = float(category.get("similarity", DEFAULT_SIMILARITY))
        return _rank_by_coverage(per_feed_items, threshold)
    return _round_robin(per_feed_items)


# ---------------------------------------------------------------------------
# Hugging Face Daily Papers
# ---------------------------------------------------------------------------

def _iso_to_epoch(value):
    return calendar.timegm(time.strptime(value[:19], "%Y-%m-%dT%H:%M:%S"))


def collect_hf_papers(category, hours_back, now_epoch):
    """HF Daily Papers API에서 기간 내 Daily Papers에 올라온 논문을 추천(upvotes) 많은 순으로 max_items개.

    Daily Papers는 날짜(UTC) 단위 목록이라, 그날의 절반 이상이 기간 안에 들어가는 날짜만 포함한다
    (예: 매일 UTC 21:37 실행이면 '오늘(UTC)' 목록 하나). 날짜마다 API를 한 번씩 부른다.
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
                    "region": "world",
                    "published_epoch": published_epoch,
                    "meta": f"추천 {upvotes}",
                    "extra_links": [{"label": "arXiv", "url": f"https://arxiv.org/abs/{paper_id}"}],
                    "excerpt": make_excerpt(paper.get("summary") or entry.get("summary")),
                    "_score": upvotes,
                }
            )
    items.sort(key=lambda x: x["_score"], reverse=True)
    logger.info("  HF Daily Papers: 기간 내 %d건", len(items))
    return items


# ---------------------------------------------------------------------------
# Hacker News (Algolia API)
# ---------------------------------------------------------------------------

def collect_hacker_news(category, hours_back, now_epoch):
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
                "region": "world",
                "published_epoch": hit.get("created_at_i") or int(now_epoch),
                "meta": f"▲{hit.get('points', 0)} · 댓글 {hit.get('num_comments', 0) or 0}",
                "extra_links": [{"label": "HN 댓글", "url": hn_link}],
                "hn_id": object_id,
            }
        )
    logger.info("  Hacker News: 후보 %d건 (points>=%d)", len(items), min_points)
    return items


COLLECTORS = {
    "rss": collect_rss_category,
    "hf_papers": collect_hf_papers,
    "hacker_news": collect_hacker_news,
}


# rss(라운드로빈)는 고른 뒤 최신순으로 보여주고, 나머지(점수·보도량 순)는 순위 그대로 보여준다.
SORT_BY_DATE = {"rss": True, "hf_papers": False, "hacker_news": False}
POOL_LIMIT = 60  # 섹션마다 중복 검사를 거친 후보를 이만큼까지만 본다 (속도)


def feed_region(feed_cfg):
    """피드의 지역: feeds.yaml의 region(kr|world), 없으면 이름에 한글이 있으면 kr."""
    region = feed_cfg.get("region")
    if region in ("kr", "world"):
        return region
    return "kr" if re.search(r"[가-힣]", feed_cfg.get("name", "")) else "world"


def _is_seen(item, key, seen, extra_keys, threshold):
    if item["link"] in seen["links"] or item["link"] in seen["history_links"]:
        return True
    if key and key in seen["history_keys"]:
        return True
    return any(is_same_story(key, k, threshold) for k in seen["keys"]) or any(
        is_same_story(key, k, threshold) for k in extra_keys
    )


def select_items(candidates, max_items, seen, threshold=DEFAULT_SIMILARITY, balance=True):
    """후보(우선순위 순)에서 max_items개를 고른다.

    - 이번 메일에서 이미 고른 기사(다른 섹션 포함)와 같은 링크·같은 사건이면 건너뛴다.
    - 최근 발송 기록(history)에 있는 링크·제목이면 건너뛴다 (매일 같은 글이 반복되지 않게).
    - balance: 국내(kr) 1개 + 해외(world) 1개를 먼저 고르고, 남은 자리는 순위대로 채운다.
      한쪽만 있으면 있는 쪽에서 채운다.

    seen: new_seen() 결과 — 메일 한 통 안에서 모든 섹션이 공유한다.
    """
    pool = []
    pool_keys = []
    skipped = 0
    for item in candidates:
        if len(pool) >= POOL_LIMIT:
            break
        key = title_key(item["title"])
        if _is_seen(item, key, seen, pool_keys, threshold):
            skipped += 1
            continue
        pool.append(item)
        pool_keys.append(key)

    picked_idx = []
    if balance:
        for region in ("kr", "world"):
            for i, item in enumerate(pool):
                if item.get("region") == region and i not in picked_idx:
                    picked_idx.append(i)
                    break
            if len(picked_idx) >= max_items:
                break
    for i in range(len(pool)):
        if len(picked_idx) >= max_items:
            break
        if i not in picked_idx:
            picked_idx.append(i)
    picked_idx = sorted(picked_idx[:max_items])  # 원래 순위 순서 유지

    picked = [pool[i] for i in picked_idx]
    for i in picked_idx:
        seen["links"].add(pool[i]["link"])
        seen["keys"].append(pool_keys[i])
    return picked, skipped


def new_seen(history_links=None, history_keys=None):
    return {
        "links": set(),
        "keys": [],
        "history_links": set(history_links or ()),
        "history_keys": set(history_keys or ()),
    }


def collect_all(config, now_epoch=None, seen=None):
    """feeds.yaml의 groups 순서대로, 각 분야(group)에 속한 섹션을 파일에 적힌 순서대로 수집한다.

    반환: [{"key", "name", "categories": [{"key","name","type","items",...}]}]
    """
    if now_epoch is None:
        now_epoch = time.time()
    if seen is None:
        seen = new_seen()
    settings = config.get("settings", {})
    default_hours = float(settings.get("default_hours_back", 36))

    groups = []
    for group in config["groups"]:
        cats = []
        for category in config.get("categories", []):
            if category.get("group") != group["key"]:
                continue
            ctype = category.get("type", "rss")
            max_items = int(category.get("max_items", group.get("max_items", 2)))
            hours_back = float(category.get("hours_back", group.get("hours_back", default_hours)))
            logger.info(
                "[%s] %s (type=%s, 최근 %d시간, 최대 %d개)", group["name"], category["name"], ctype, hours_back, max_items
            )
            category = {**category, "_global_exclude": settings.get("exclude_keywords")}
            candidates = COLLECTORS[ctype](category, hours_back, now_epoch)
            threshold = float(category.get("similarity", DEFAULT_SIMILARITY))
            items, skipped = select_items(candidates, max_items, seen, threshold, balance=category.get("balance", True))
            if skipped:
                logger.info("  이미 보냈거나 같은 사건/중복 %d건 제외", skipped)
            if SORT_BY_DATE[ctype] and category.get("rank") != "coverage":
                items.sort(key=lambda x: x["published_epoch"], reverse=True)
            for item in items:
                item.pop("_score", None)
            result = {"key": category["key"], "name": category["name"], "type": ctype, "items": items}
            if category.get("summary_style"):
                result["summary_style"] = category["summary_style"]
            cats.append(result)
        groups.append({"key": group["key"], "name": group["name"], "categories": cats})
    return groups


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cfg = load_config(Path(__file__).resolve().parent.parent / "feeds.yaml")
    for g in collect_all(cfg):
        for cat in g["categories"]:
            print(g["name"], cat["name"], len(cat["items"]))
