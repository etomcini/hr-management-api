from email.message import EmailMessage

import aiosmtplib

from app.core.config import settings


async def send_email(
    to_email: str,
    subject: str,
    text_content: str,
    html_content: str | None = None,
) -> None:
    message = EmailMessage()

    message["From"] = f"{settings.mail_from_name} <{settings.mail_from_email}>"
    message["To"] = to_email
    message["Subject"] = subject

    message.set_content(text_content)

    if html_content is not None:
        message.add_alternative(
            html_content,
            subtype="html",
        )

    await aiosmtplib.send(
        message,
        hostname=settings.mail_server,
        port=settings.mail_port,
        username=settings.mail_username,
        password=settings.mail_password.get_secret_value(),
        start_tls=settings.mail_start_tls,
        timeout=30,
    )
