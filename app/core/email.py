from email.message import EmailMessage
from urllib.parse import urlencode

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
    )


async def send_password_reset_email(
    to_email: str,
    reset_token: str,
) -> None:
    query = urlencode(
        {
            "token": reset_token,
        }
    )

    reset_url = f"{settings.frontend_url.rstrip('/')}/reset-password?{query}"

    subject = "Reset your password"

    text_content = f"""
You requested a password reset for your HR Application account.

Use the following link to reset your password:

{reset_url}

This link expires in {settings.password_reset_token_expire_minutes} minutes.

If you did not request a password reset, you can ignore this email.
""".strip()

    html_content = f"""
    <html>
        <body>
            <h2>Reset your password</h2>

            <p>
                You requested a password reset for your
                HR Application account.
            </p>

            <p>
                <a href="{reset_url}">
                    Reset password
                </a>
            </p>

            <p>
                This link expires in
                {settings.password_reset_token_expire_minutes}
                minutes.
            </p>

            <p>
                If you did not request a password reset,
                you can ignore this email.
            </p>
        </body>
    </html>
    """.strip()

    await send_email(
        to_email=to_email,
        subject=subject,
        text_content=text_content,
        html_content=html_content,
    )
