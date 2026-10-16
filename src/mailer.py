"""SMTP(앱 비밀번호)로 HTML 메일 발송. 계정 정보는 전부 환경변수에서 읽는다.

보내는 주소(GMAIL_USER)의 도메인으로 SMTP 서버를 고른다: @naver.com → 네이버, 그 밖 → Gmail.
(이름은 GMAIL_USER지만 네이버 주소를 넣어도 된다. SMTP_HOST 환경변수가 있으면 그걸 우선한다.)
받는 주소(MAIL_TO)는 쉼표로 여러 개 넣을 수 있다.
"""
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

SMTP_PORT = 465
SMTP_HOSTS = {
    "naver.com": "smtp.naver.com",
    "gmail.com": "smtp.gmail.com",
}


def smtp_host_for(user):
    override = os.environ.get("SMTP_HOST")
    if override:
        return override
    domain = user.rsplit("@", 1)[-1].lower()
    return SMTP_HOSTS.get(domain, "smtp.gmail.com")


def recipients(mail_to):
    return [addr.strip() for addr in mail_to.split(",") if addr.strip()]


def get_credentials_from_env():
    """GMAIL_USER / GMAIL_APP_PASSWORD / MAIL_TO 환경변수를 읽는다. 하나라도 없으면 None 반환."""
    user = os.environ.get("GMAIL_USER")
    app_password = os.environ.get("GMAIL_APP_PASSWORD")
    mail_to = os.environ.get("MAIL_TO")
    if not (user and app_password and mail_to):
        return None
    return {"user": user, "app_password": app_password, "mail_to": mail_to}


def send_html_mail(subject, html_body, plain_fallback, creds):
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = creds["user"]
    to_list = recipients(creds["mail_to"])
    message["To"] = ", ".join(to_list)
    message.attach(MIMEText(plain_fallback, "plain", "utf-8"))
    message.attach(MIMEText(html_body, "html", "utf-8"))

    host = smtp_host_for(creds["user"])
    with smtplib.SMTP_SSL(host, SMTP_PORT) as server:
        server.login(creds["user"], creds["app_password"])
        server.sendmail(creds["user"], to_list, message.as_string())

    logger.info("메일 발송 완료 (%s) -> %s", host, ", ".join(to_list))
