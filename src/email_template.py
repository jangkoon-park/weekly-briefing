"""data/briefing.json (+ 선택적 번역·요약, 이번 주 흐름)을 가벼운 HTML 메일로 변환.

- 이미지 없음, 스타일은 꼭 필요한 인라인 스타일만 (지메일은 HTML 102KB를 넘으면 메일을 잘라서 보여줌)
- (월요일) 맨 위 "이번 주 흐름": 큰 방향 3줄 + 분야별 움직임 8줄, 맨 아래 "섹션별 상세 동향" 34줄
- 목차: 8개 분야 + 건수, 누르면 해당 분야로 이동
- 기사마다 🇰🇷 국내 / 🌍 세계 표시, 새 글이 없는 섹션은 "새 소식 없음"
- fit_to_size(): HTML이 한도를 넘으면 기사가 가장 많은 섹션부터 한 개씩 줄여서 맞춘다
"""
import copy
import html
import logging

logger = logging.getLogger(__name__)

FONT = "-apple-system,'Segoe UI',Roboto,'Apple SD Gothic Neo','Malgun Gothic',sans-serif"
FLAG = {"kr": "🇰🇷", "world": "🌍"}
SIDE_LABEL = {"kr": "🇰🇷 한국", "world": "🌍 세계"}
CHANGE = {"new": "🆕", "continue": "➡️", "down": "🔻"}
NUMS = "①②③"


def _esc(text):
    return html.escape(text or "", quote=True)


def _item_html(item, extra):
    """extra: data/enrich.json의 이 기사 항목 ({title_ko, summary, debate}, 없으면 {})."""
    meta = [_esc(item.get("source")), _esc(item.get("published", "")[:16])]
    if item.get("meta"):
        meta.append(_esc(item["meta"]))
    for link in item.get("extra_links", []):
        meta.append(f'<a href="{_esc(link["url"])}" style="color:#555">{_esc(link["label"])}</a>')

    title_ko = extra.get("title_ko")
    if title_ko and title_ko.strip() == item["title"].strip():
        title_ko = None
    flag = FLAG.get(item.get("region"), "")
    out = (
        f'<li style="margin:0 0 16px">{flag} <a href="{_esc(item["link"])}" style="color:#1a0dab;'
        f'text-decoration:none;font-weight:600;font-size:18px">{_esc(title_ko or item["title"])}</a>'
    )
    if title_ko:
        # 번역 제목 아래에 원제를 작게
        out += f'<br><span style="font-size:14px;color:#777">{_esc(item["title"])}</span>'
    out += f'<br><span style="font-size:14px;color:#888">{" · ".join(meta)}</span>'
    for key in ("summary", "debate"):
        if extra.get(key):
            out += f'<br><span style="color:#333">{_esc(extra[key]).replace(chr(10), "<br>")}</span>'
    return out + "</li>"


def _extra(enrich, item):
    value = enrich.get(item.get("eid")) if item.get("eid") else None
    return value if isinstance(value, dict) else {}


def total_items(briefing):
    return sum(len(c["items"]) for s in briefing["sections"] for c in s["categories"])


def _trend_side(side, line, show_basis=False):
    """이번 주 흐름 한 줄의 🇰🇷/🌍 한쪽. line: {text, links, change, basis}"""
    if not line:
        return ""
    change = CHANGE.get(line.get("change"), "")
    basis = f' <span style="color:#888">({_esc(line["basis"])})</span>' if show_basis and line.get("basis") else ""
    links = " ".join(
        f'<a href="{_esc(link["url"])}">{NUMS[i]}</a>' for i, link in enumerate(line.get("links", [])[:3])
    )
    return (
        f'<div style="margin:2px 0 2px 8px">{SIDE_LABEL[side]} {change} {_esc(line["text"])}{basis}'
        f'{" " + links if links else ""}</div>'
    )


def _trend_entry(label, sides, show_basis=False):
    if not sides or not any(sides.get(s) for s in ("kr", "world")):
        return ""
    body = "".join(_trend_side(s, sides.get(s), show_basis) for s in ("kr", "world"))
    return f'<div style="margin:8px 0"><b>{_esc(label)}</b>{body}</div>'


def _trend_top(trend, config):
    areas = "".join(
        _trend_entry(a["name"], trend.get("areas", {}).get(a["key"]), show_basis=True)
        for a in config.get("trend_areas", [])
    )
    groups = "".join(
        _trend_entry(g["name"], trend.get("groups", {}).get(g["key"])) for g in config.get("groups", [])
    )
    return (
        '<div style="margin:16px 0;padding:10px 12px;border:2px solid #111">'
        '<h2 style="margin:0 0 6px;font-size:20px">📈 이번 주 흐름</h2>'
        '<div style="font-size:13px;color:#888">🆕 새로 생김 · ➡️ 계속 · 🔻 줄어듦 (지난주 대비) · ①②③ 근거 기사</div>'
        f'<h3 style="margin:12px 0 4px;font-size:17px">큰 방향</h3>{areas}'
        f'<h3 style="margin:12px 0 4px;font-size:17px">분야별 움직임</h3>{groups}'
        '<div style="font-size:13px;color:#888;margin-top:8px">섹션별 상세 동향은 메일 맨 아래에 있습니다.</div>'
        "</div>"
    )


def _trend_bottom(trend, config):
    sections = trend.get("sections", {})
    names = {c["key"]: c["name"] for c in config.get("categories", [])}
    rows = []
    for group in config.get("groups", []):
        entries = "".join(
            _trend_entry(names[c["key"]], sections.get(c["key"]))
            for c in config.get("categories", [])
            if c.get("group") == group["key"]
        )
        if entries:
            rows.append(f'<h3 style="margin:16px 0 4px;font-size:17px">{_esc(group["name"])}</h3>{entries}')
    if not rows:
        return ""
    return (
        '<h2 id="trend-detail" style="margin:32px 0 0;padding:6px 10px;background:#444;color:#fff;font-size:20px">'
        '<a name="trend-detail"></a>섹션별 상세 동향 (이번 주)</h2>' + "".join(rows)
    )


def build_html(briefing, heading, date_label, enrich=None, trend=None, config=None):
    enrich = enrich or {}
    config = config or {}

    toc = " · ".join(
        f'<a href="#g-{_esc(g["key"])}" style="color:#1a0dab">{_esc(g["title"])}</a> '
        f'{sum(len(c["items"]) for c in g["categories"])}'
        for g in briefing["sections"]
    )
    body_parts = []
    for group in briefing["sections"]:
        anchor = f'g-{_esc(group["key"])}'
        body_parts.append(
            f'<h2 id="{anchor}" style="margin:28px 0 0;padding:6px 10px;background:#111;color:#fff;font-size:20px">'
            f'<a name="{anchor}"></a>{_esc(group["title"])}</h2>'
        )
        for c in group["categories"]:
            if c["items"]:
                inner = '<ul style="margin:0;padding-left:20px">' + "".join(
                    _item_html(i, _extra(enrich, i)) for i in c["items"]
                ) + "</ul>"
            else:
                inner = '<div style="color:#999;margin:0 0 8px">새 소식 없음</div>'
            body_parts.append(
                f'<h3 style="margin:20px 0 8px;font-size:18px;border-bottom:2px solid #111">'
                f'{_esc(c["name"])} ({len(c["items"])})</h3>{inner}'
            )

    return (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{_esc(heading)}</title></head>"
        '<body style="margin:0;padding:12px">'
        # 지메일은 body 스타일을 지우므로 기본 글꼴·크기는 감싸는 div에 둔다
        f'<div style="max-width:640px;margin:0 auto;font-family:{FONT};font-size:16px;line-height:1.55;color:#222">'
        f'<h1 style="margin:0;font-size:24px">{_esc(heading)}</h1>'
        f'<div style="color:#888;font-size:14px">{_esc(date_label)}</div>'
        f'{_trend_top(trend, config) if trend else ""}'
        f'<div style="margin:12px 0;padding:8px 10px;background:#f4f4f4;font-size:16px;line-height:1.8">{toc}</div>'
        f'{"".join(body_parts)}'
        f'{_trend_bottom(trend, config) if trend else ""}'
        '<p style="margin-top:24px;color:#aaa;font-size:13px">feeds.yaml에서 분야·섹션·피드·개수를 바꿀 수 있습니다.</p>'
        "</div></body></html>"
    )


def html_size(text):
    return len(text.encode("utf-8"))


def fit_to_size(briefing, render, max_bytes):
    """render(briefing) 결과가 max_bytes 이하가 될 때까지 가장 많은 분야부터 한 개씩 줄인다.

    반환: (html, 줄인 briefing)
    """
    trimmed = copy.deepcopy(briefing)
    html_text = render(trimmed)
    size = html_size(html_text)
    logger.info("HTML 크기: %.1fKB (한도 %.1fKB)", size / 1024, max_bytes / 1024)
    steps = 0
    while size > max_bytes:
        cats = [c for s in trimmed["sections"] for c in s["categories"] if len(c["items"]) > 1]
        if not cats:
            logger.warning("더 줄일 수 있는 분야가 없습니다. %.1fKB 그대로 보냅니다.", size / 1024)
            break
        biggest = max(cats, key=lambda c: len(c["items"]))
        biggest["items"].pop()
        steps += 1
        html_text = render(trimmed)
        size = html_size(html_text)
    if steps:
        logger.info("한도 초과로 %d개를 줄여 %.1fKB로 맞췄습니다.", steps, size / 1024)
        for s in trimmed["sections"]:
            for c in s["categories"]:
                logger.info("  %s | %s | %d건", s["title"], c["name"], len(c["items"]))
    return html_text, trimmed
