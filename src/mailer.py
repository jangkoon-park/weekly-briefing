"""Gmail SMTP(앱 비밀번호)로 HTML 메일 발송. 계정 정보는 전부 환경변수에서 읽는다."""
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


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
    message["To"] = creds["mail_to"]
    message.attach(MIMEText(plain_fallback, "plain", "utf-8"))
    message.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
        server.login(creds["user"], creds["app_password"])
        server.sendmail(creds["user"], [creds["mail_to"]], message.as_string())

    logger.info("메일 발송 완료 -> %s", creds["mail_to"])
