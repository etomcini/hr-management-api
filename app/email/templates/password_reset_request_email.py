from html import escape
from urllib.parse import urlencode

from app.core.config import settings
from app.email.templates.schemas import EmailContent


def build_password_reset_email(
    reset_token: str,
) -> EmailContent:
    query = urlencode({"token": reset_token})

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
                <a href="{escape(reset_url, quote=True)}">
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

    return EmailContent(
        subject=subject,
        text_content=text_content,
        html_content=html_content,
    )
