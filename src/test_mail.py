"""발송 확인용 테스트 메일 1통 보내기 (기사 수집·Claude·발송 기록 없음).

  python -m src.test_mail

GMAIL_USER / GMAIL_APP_PASSWORD / MAIL_TO 환경변수(Actions에서는 Secrets)로 GMAIL_USER → MAIL_TO에 보낸다.
결과는 로그에 "✅ 테스트 메일 발송 성공" 또는 "❌ 테스트 메일 발송 실패"로 남기고, 실패하면 종료 코드 1로 끝난다
(Actions 실행이 빨간색으로 표시됨). data/history는 읽지도 쓰지도 않는다.
"""
import logging
import smtplib
import sys
from datetime import datetime, timedelta, timezone

from src.mailer import get_credentials_from_env, send_html_mail

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))


def main():
    now = datetime.now(KST)
    subject = f"[브리핑 테스트] 발송 확인 {now.strftime('%Y-%m-%d %H:%M')}"

    creds = get_credentials_from_env()
    if creds is None:
        logger.error("❌ 테스트 메일 발송 실패: GMAIL_USER / GMAIL_APP_PASSWORD / MAIL_TO Secret 중 비어 있는 값이 있습니다.")
        return 1

    plain = (
        f"데일리 브리핑 발송 설정이 정상입니다.\n"
        f"보낸 시각: {now.strftime('%Y-%m-%d %H:%M')} KST\n"
        f"이 메일은 수동 실행의 test_mail 옵션으로 보낸 테스트 메일이며, 기사는 포함되지 않습니다."
    )
    html = (
        '<div style="font-family:-apple-system,\'Apple SD Gothic Neo\',\'Malgun Gothic\',sans-serif;'
        'font-size:16px;line-height:1.6;color:#222">'
        "<p><b>데일리 브리핑 발송 설정이 정상입니다.</b></p>"
        f"<p>보낸 시각: {now.strftime('%Y-%m-%d %H:%M')} KST</p>"
        '<p style="color:#888;font-size:14px">이 메일은 수동 실행의 test_mail 옵션으로 보낸 테스트 메일이며, '
        "기사는 포함되지 않습니다.</p></div>"
    )

    logger.info("테스트 메일 발송 시도: 제목 \"%s\"", subject)
    try:
        send_html_mail(subject, html, plain, creds)
    except smtplib.SMTPAuthenticationError as exc:
        logger.error(
            "❌ 테스트 메일 발송 실패 (로그인 오류): GMAIL_USER와 GMAIL_APP_PASSWORD(16자리 앱 비밀번호)를 확인하세요. %s", exc
        )
        return 1
    except Exception as exc:  # noqa: BLE001 - 어떤 오류든 실패로 분명히 남긴다
        logger.error("❌ 테스트 메일 발송 실패: %s: %s", type(exc).__name__, exc)
        return 1

    logger.info("✅ 테스트 메일 발송 성공: %s → %s", creds["user"], creds["mail_to"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
