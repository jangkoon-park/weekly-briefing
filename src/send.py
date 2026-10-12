"""2단계: HTML 메일을 만들고, Secrets가 있으면 발송, 없으면 로컬에 저장만 한다(dry-run)."""
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

from src.email_template import build_html
from src.mailer import get_credentials_from_env, send_html_mail

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
KST = timezone(timedelta(hours=9))


def main():
    now_kst = datetime.now(KST)
    date_label = now_kst.strftime("%Y-%m-%d (%a) 기준")
    html_body = build_html(date_label)

    preview_path = ROOT / "data" / "preview.html"
    preview_path.write_text(html_body, encoding="utf-8")
    logger.info("미리보기 저장: %s", preview_path)

    creds = get_credentials_from_env()
    if creds is None:
        logger.warning(
            "GMAIL_USER / GMAIL_APP_PASSWORD / MAIL_TO 중 일부가 없어 발송을 건너뜁니다 "
            "(dry-run). %s 파일을 열어 결과를 확인하세요.",
            preview_path,
        )
        return

    subject = f"[주간 뉴스 브리핑] {now_kst.strftime('%Y-%m-%d')}"
    plain_fallback = "HTML을 지원하는 메일 클라이언트로 열어주세요."
    send_html_mail(subject, html_body, plain_fallback, creds)


if __name__ == "__main__":
    main()
