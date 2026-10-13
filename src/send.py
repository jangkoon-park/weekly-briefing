"""2단계: data/briefing.json으로 HTML 메일을 만들고, Secrets가 있으면 발송, 없으면 미리보기만 저장(dry-run).

  python -m src.send                        # Secrets가 있으면 발송 + 발송 기록(data/history) 저장
  python -m src.send --dry-run              # 발송하지 않고 data/preview.html만 생성 (기록도 저장 안 함)
  python -m src.send --dry-run --save-history   # 테스트용: 발송 없이 기록만 저장
"""
import argparse
import json
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from src import history
from src.email_template import build_html, fit_to_size, total_items
from src.feeds import load_config
from src.mailer import get_credentials_from_env, send_html_mail

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
KST = timezone(timedelta(hours=9))


def _load_json(path, default):
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_parts(paths):
    """여러 결과 파일을 읽어 dict로 합친다. 깨진 파일은 경고만 남기고 건너뛴다."""
    merged = {}
    for path in paths:
        try:
            part = _load_json(path, {})
        except ValueError as exc:
            logger.warning("%s을 읽을 수 없어 건너뜁니다: %s", path.name, exc)
            continue
        if isinstance(part, dict):
            for key, value in part.items():
                if isinstance(value, dict) and isinstance(merged.get(key), dict):
                    merged[key].update(value)
                else:
                    merged[key] = value
    return merged


def drop_duplicates(briefing, enrich):
    """Claude가 dup_of(앞 기사와 같은 사건)로 표시한 기사(가리키는 기사가 실제로 앞에 있을 때만)와
    ad(광고·보도자료성)로 표시한 기사를 뺀다."""
    kept_ids = set()
    removed = 0
    ads = 0
    for section in briefing["sections"]:
        for cat in section["categories"]:
            kept = []
            for item in cat["items"]:
                info = enrich.get(item.get("eid"))
                dup_of = info.get("dup_of") if isinstance(info, dict) else None
                if dup_of and dup_of in kept_ids:
                    removed += 1
                    continue
                if isinstance(info, dict) and info.get("ad") is True:
                    ads += 1
                    continue
                kept.append(item)
                kept_ids.add(item.get("eid"))
            cat["items"] = kept
    if removed:
        logger.info("같은 사건 중복 %d건 제외 (Claude 판단)", removed)
    if ads:
        logger.info("광고·보도자료성 %d건 제외 (Claude 판단)", ads)


def load_trend():
    """Claude가 만든 data/trend.json(+trend_sections.json)을 읽고, 근거 기사 id(refs)를 실제 링크로 바꾼다.

    Claude가 URL을 직접 쓰지 않고 id만 쓰게 해서 링크가 지어내질 수 없게 한다.
    반환: {"areas": {...}, "groups": {...}, "sections": {...}} 또는 None
    """
    trend = _load_parts([DATA_DIR / "trend.json", DATA_DIR / "trend_sections.json"])
    if not trend:
        return None
    try:
        articles = {a["id"]: a for a in _load_json(DATA_DIR / "trend_input.json", {}).get("articles", [])}
    except ValueError:
        articles = {}

    def resolve_line(line):
        if not isinstance(line, dict) or not line.get("text"):
            return None
        links = []
        for ref in line.get("refs") or []:
            art = articles.get(ref)
            if art and art.get("link"):
                links.append({"title": art.get("title_ko") or art.get("title") or ref, "url": art["link"]})
        change = line.get("change") if line.get("change") in ("new", "continue", "down") else None
        out = {"text": str(line["text"]), "links": links[:3], "change": change}
        if line.get("basis"):
            out["basis"] = str(line["basis"])
        return out

    resolved = {}
    for layer in ("areas", "groups", "sections"):
        entries = trend.get(layer)
        if not isinstance(entries, dict):
            continue
        resolved[layer] = {}
        for key, sides in entries.items():
            if not isinstance(sides, dict):
                continue
            resolved[layer][key] = {side: resolve_line(sides.get(side)) for side in ("kr", "world")}
    if not resolved.get("areas") and not resolved.get("groups"):
        logger.warning("이번 주 흐름 결과가 비어 있거나 형식이 맞지 않아 메일에 넣지 않습니다.")
        return None
    return resolved


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="발송하지 않고 미리보기만 저장")
    parser.add_argument("--save-history", action="store_true", help="dry-run이어도 발송 기록을 저장 (테스트용)")
    args = parser.parse_args()

    config = load_config(ROOT / "feeds.yaml")
    briefing = _load_json(DATA_DIR / "briefing.json", None)
    if briefing is None:
        raise SystemExit("data/briefing.json이 없습니다. 먼저 python -m src.collect를 실행하세요.")

    if total_items(briefing) == 0:
        logger.warning("모든 섹션에 새 글이 없어 메일을 보내지 않습니다.")
        return

    # (선택) Claude 번역·요약 결과. enrich.json 하나 또는 enrich_out_N.json 여러 개. 없거나 깨져 있으면 원문 그대로
    enrich = _load_parts([DATA_DIR / "enrich.json", *sorted(DATA_DIR.glob("enrich_out_*.json"))])
    if enrich:
        logger.info("번역·요약 결과 %d건 반영", len(enrich))
        drop_duplicates(briefing, enrich)
        if total_items(briefing) == 0:
            logger.warning("모든 섹션에 새 글이 없어 메일을 보내지 않습니다.")
            return

    trend = load_trend() if briefing.get("weekly_trend") else None
    if briefing.get("weekly_trend") and trend is None:
        logger.warning("월요일이지만 이번 주 흐름 결과(data/trend.json)가 없어 흐름 없이 보냅니다.")

    now_kst = datetime.now(KST)
    title = "데일리 브리핑 · 이번 주 흐름" if trend else "데일리 브리핑"
    subject = f"[{title}] {now_kst.strftime('%Y-%m-%d')}"
    date_label = now_kst.strftime("%Y-%m-%d (%a) %H:%M KST")

    max_bytes = int(float(config.get("settings", {}).get("max_html_kb", 100)) * 1024)
    html_body, final_briefing = fit_to_size(
        briefing,
        lambda b: build_html(b, title, date_label, enrich, trend, config),
        max_bytes,
    )

    preview_path = DATA_DIR / "preview.html"
    preview_path.write_text(html_body, encoding="utf-8")
    logger.info("미리보기 저장: %s (%.1fKB)", preview_path, len(html_body.encode("utf-8")) / 1024)

    def save_records():
        today = date.fromisoformat(briefing["date"])
        history.save_day(today, final_briefing, enrich)
        if trend:
            history.save_trend(today, trend)
        history.prune(today, int(config.get("settings", {}).get("history_days", 35)))

    if args.dry_run:
        logger.info("--dry-run: 발송하지 않습니다. 제목: %s", subject)
        if args.save_history:
            save_records()
        return

    creds = get_credentials_from_env()
    if creds is None:
        logger.warning(
            "GMAIL_USER / GMAIL_APP_PASSWORD / MAIL_TO 중 일부가 없어 발송을 건너뜁니다 (dry-run). 제목: %s",
            subject,
        )
        return

    plain_fallback = "HTML을 지원하는 메일 클라이언트로 열어주세요."
    send_html_mail(subject, html_body, plain_fallback, creds)
    save_records()


if __name__ == "__main__":
    main()
