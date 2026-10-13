"""data/briefing.json (+ 선택적 요약 파일)을 가벼운 HTML 메일로 변환.

- 이미지 없음, 스타일은 꼭 필요한 인라인 스타일만 (지메일은 HTML 102KB를 넘으면 메일을 잘라서 보여줌)
- 맨 위 목차: 분야명 + 건수, 누르면 해당 섹션으로 이동
- 글이 없는 분야는 섹션째 생략
- fit_to_size(): HTML이 한도를 넘으면 분야별 개수를 하나씩 줄여서 맞춘다
"""
import copy
import html
import logging

logger = logging.getLogger(__name__)

FONT = "-apple-system,'Segoe UI',Roboto,'Apple SD Gothic Neo','Malgun Gothic',sans-serif"


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
    out = (
        f'<li style="margin:0 0 16px"><a href="{_esc(item["link"])}" style="color:#1a0dab;'
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


def _visible(briefing):
    """글이 있는 분야만 남긴 (section, [categories]) 목록."""
    result = []
    for section in briefing["sections"]:
        cats = [c for c in section["categories"] if c["items"]]
        if cats:
            result.append((section, cats))
    return result


def total_items(briefing):
    return sum(len(c["items"]) for s in briefing["sections"] for c in s["categories"])


def build_html(briefing, heading, date_label, enrich=None):
    enrich = enrich or {}
    visible = _visible(briefing)

    toc_parts = []
    body_parts = []
    for section, cats in visible:
        sid = section["schedule"]
        toc_links = " · ".join(
            f'<a href="#{sid}-{_esc(c["key"])}" style="color:#1a0dab">{_esc(c["name"])}</a> {len(c["items"])}'
            for c in cats
        )
        toc_parts.append(f'<p style="margin:4px 0"><b>{_esc(section["title"])}</b><br>{toc_links}</p>')

        body_parts.append(
            f'<h2 style="margin:28px 0 0;padding:6px 10px;background:#111;color:#fff;font-size:20px">'
            f'{_esc(section["title"])}</h2>'
        )
        for c in cats:
            anchor = f'{sid}-{_esc(c["key"])}'
            items = "".join(
                _item_html(i, _extra(enrich, i))
                for i in c["items"]
            )
            body_parts.append(
                f'<h3 id="{anchor}" style="margin:24px 0 10px;font-size:20px;border-bottom:2px solid #111">'
                f'<a name="{anchor}"></a>{_esc(c["name"])} ({len(c["items"])})</h3>'
                f'<ul style="margin:0;padding-left:20px">{items}</ul>'
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
        f'<div style="margin:12px 0;padding:8px 10px;background:#f4f4f4;font-size:16px;line-height:1.7">{"".join(toc_parts)}</div>'
        f'{"".join(body_parts)}'
        '<p style="margin-top:24px;color:#aaa;font-size:13px">feeds.yaml에서 분야·피드·개수를 바꿀 수 있습니다.</p>'
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
                logger.info("  %s | %s | %d건", s["schedule"], c["name"], len(c["items"]))
    return html_text, trimmed
