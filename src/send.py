"""2단계: data/briefing.json으로 HTML 메일을 만들고, Secrets가 있으면 발송, 없으면 미리보기만 저장(dry-run).

  python -m src.send             # Secrets가 있으면 발송
  python -m src.send --dry-run   # 발송하지 않고 data/preview.html만 생성
"""
import argparse
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.email_template import build_html, fit_to_size, total_items
from src.feeds import load_config
from src.mailer import get_credentials_from_env, send_html_mail

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
KST = timezone(timedelta(hours=9))

SUBJECT_PREFIX = {"daily": "데일리 브리핑", "weekly": "주간 브리핑", "both": "데일리+주간 브리핑"}


def _load_json(path, default):
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def drop_duplicates(briefing, enrich):
    """Claude가 dup_of(앞 기사와 같은 사건)로 표시한 기사를 뺀다. 가리키는 기사가 실제로 앞에 있을 때만."""
    kept_ids = set()
    removed = 0
    for section in briefing["sections"]:
        for cat in section["categories"]:
            kept = []
            for item in cat["items"]:
                info = enrich.get(item.get("eid"))
                dup_of = info.get("dup_of") if isinstance(info, dict) else None
                if dup_of and dup_of in kept_ids:
                    removed += 1
                    continue
                kept.append(item)
                kept_ids.add(item.get("eid"))
            cat["items"] = kept
    if removed:
        logger.info("같은 사건 중복 %d건 제외 (Claude 판단)", removed)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="발송하지 않고 미리보기만 저장")
    args = parser.parse_args()

    config = load_config(ROOT / "feeds.yaml")
    briefing = _load_json(DATA_DIR / "briefing.json", None)
    if briefing is None:
        raise SystemExit("data/briefing.json이 없습니다. 먼저 python -m src.collect를 실행하세요.")

    if total_items(briefing) == 0:
        logger.warning("모든 분야에 새 글이 없어 메일을 보내지 않습니다.")
        return

    now_kst = datetime.now(KST)
    title = SUBJECT_PREFIX[briefing["mode"]]
    subject = f"[{title}] {now_kst.strftime('%Y-%m-%d')}"
    date_label = now_kst.strftime("%Y-%m-%d (%a) %H:%M KST")
    # (선택) Claude 번역·요약 결과. 없거나 깨져 있으면 원문 그대로 보냄
    try:
        enrich = _load_json(DATA_DIR / "enrich.json", {})
    except ValueError as exc:
        logger.warning("data/enrich.json을 읽을 수 없어 번역·요약 없이 보냅니다: %s", exc)
        enrich = {}
    if enrich:
        logger.info("번역·요약 결과 %d건 반영", len(enrich))
        drop_duplicates(briefing, enrich)
        if total_items(briefing) == 0:
            logger.warning("모든 분야에 새 글이 없어 메일을 보내지 않습니다.")
            return

    max_bytes = int(float(config.get("settings", {}).get("max_html_kb", 100)) * 1024)
    html_body, _ = fit_to_size(
        briefing,
        lambda b: build_html(b, title, date_label, enrich),
        max_bytes,
    )

    preview_path = DATA_DIR / "preview.html"
    preview_path.write_text(html_body, encoding="utf-8")
    logger.info("미리보기 저장: %s (%.1fKB)", preview_path, len(html_body.encode("utf-8")) / 1024)

    if args.dry_run:
        logger.info("--dry-run: 발송하지 않습니다. 제목: %s", subject)
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


if __name__ == "__main__":
    main()
