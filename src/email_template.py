"""data/articles.json, data/hn.json (+ 선택적 요약 파일)을 모바일 친화적 HTML 메일로 변환."""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"


def _load_json(path, default):
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _esc(text):
    return html.escape(text or "")


def _article_row(item, summary):
    title = _esc(item["title"])
    link = _esc(item["link"])
    source = _esc(item["source"])
    published = _esc(item["published"])
    summary_html = ""
    if summary:
        summary_html = (
            f'<div style="margin-top:4px;font-size:13px;color:#444;line-height:1.5;">{_esc(summary)}</div>'
        )
    return f"""
    <tr>
      <td style="padding:10px 0;border-bottom:1px solid #eee;">
        <a href="{link}" style="font-size:15px;font-weight:600;color:#1a0dab;text-decoration:none;line-height:1.4;">{title}</a>
        <div style="margin-top:2px;font-size:12px;color:#888;">{source} · {published}</div>
        {summary_html}
      </td>
    </tr>
    """


def _category_section(category, summaries):
    items = category["items"]
    if not items:
        rows = '<tr><td style="padding:10px 0;color:#999;font-size:13px;">최근 7일 내 수집된 기사가 없습니다.</td></tr>'
    else:
        rows = "".join(
            _article_row(item, summaries.get(item["link"])) for item in items
        )
    return f"""
    <tr>
      <td style="padding:20px 16px 4px 16px;">
        <h2 style="margin:0 0 4px 0;font-size:17px;color:#111;">{_esc(category["name"])}</h2>
      </td>
    </tr>
    <tr>
      <td style="padding:0 16px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
          {rows}
        </table>
      </td>
    </tr>
    """


def _hn_row(item, hn_summary):
    title = _esc(item["title"])
    url = _esc(item["url"])
    hn_link = _esc(item["hn_link"])
    points = item.get("points", 0)
    comments = item.get("num_comments", 0)
    summary_html = ""
    if hn_summary:
        summary_html = (
            '<div style="margin-top:6px;font-size:13px;color:#444;line-height:1.6;'
            'background:#f7f7f7;border-radius:6px;padding:8px 10px;">'
            f"{_esc(hn_summary).replace(chr(10), '<br>')}</div>"
        )
    return f"""
    <tr>
      <td style="padding:10px 0;border-bottom:1px solid #eee;">
        <a href="{url}" style="font-size:15px;font-weight:600;color:#1a0dab;text-decoration:none;line-height:1.4;">{title}</a>
        <div style="margin-top:2px;font-size:12px;color:#888;">
          ▲ {points}점 · 댓글 {comments}개 ·
          <a href="{hn_link}" style="color:#888;">HN 댓글 보기</a>
        </div>
        {summary_html}
      </td>
    </tr>
    """


def _hn_section(hn_items, hn_summaries):
    if not hn_items:
        rows = '<tr><td style="padding:10px 0;color:#999;font-size:13px;">조건(최근 7일, 200점 이상)을 만족하는 글이 없습니다.</td></tr>'
    else:
        rows = "".join(_hn_row(item, hn_summaries.get(item["id"])) for item in hn_items)
    return f"""
    <tr>
      <td style="padding:20px 16px 4px 16px;">
        <h2 style="margin:0 0 4px 0;font-size:17px;color:#111;">Hacker News Top {len(hn_items)}</h2>
        <div style="font-size:12px;color:#888;">최근 7일 · 200점 이상</div>
      </td>
    </tr>
    <tr>
      <td style="padding:0 16px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
          {rows}
        </table>
      </td>
    </tr>
    """


def build_html(date_label):
    articles = _load_json(DATA_DIR / "articles.json", {"categories": []})
    hn = _load_json(DATA_DIR / "hn.json", {"items": []})
    summaries = _load_json(DATA_DIR / "summaries.json", {})
    hn_summaries = _load_json(DATA_DIR / "hn_summaries.json", {})

    sections = "".join(
        _category_section(cat, summaries.get(cat["key"], {})) for cat in articles["categories"]
    )
    hn_section = _hn_section(hn["items"], hn_summaries)

    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>주간 뉴스 브리핑</title>
</head>
<body style="margin:0;padding:0;background:#f2f2f2;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f2f2f2;">
    <tr>
      <td align="center" style="padding:16px 0;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;border-radius:8px;overflow:hidden;">
          <tr>
            <td style="padding:20px 16px;background:#111;">
              <h1 style="margin:0;color:#fff;font-size:19px;">주간 뉴스 브리핑</h1>
              <div style="color:#ccc;font-size:12px;margin-top:4px;">{_esc(date_label)}</div>
            </td>
          </tr>
          {sections}
          {hn_section}
          <tr>
            <td style="padding:16px;color:#aaa;font-size:11px;text-align:center;">
              feeds.yaml을 수정하면 수집 대상을 바꿀 수 있습니다.
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""
