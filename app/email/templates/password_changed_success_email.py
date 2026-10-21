from app.email.templates.schemas import EmailContent


def build_password_change_success_email() -> EmailContent:
    subject = "You changed your password successfully"

    text_content = (
        "Hello,\n\n"
        "You changed your account password successfully.\n\n"
        "If you made this change, no further action is required.\n\n"
        "If you did not change your password, please contact "
        "administrator immediately.\n\n"
        "For security reasons, your existing login sessions "
        "have been signed out.\n\n"
        "Best regards,\n"
        "Technical Support Team"
    )

    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <body>
        <h2>You changed your password successfully</h2>

        <p>Hello,</p>

        <p>
            You changed your account password successfully.
        </p>

        <p>
            If you made this change, no further action
            is required.
        </p>

        <p>
            <strong>Didn't change your password?</strong>
            Please contact administrator immediately.
        </p>

        <p>
            For security reasons, your existing login
            sessions have been signed out.
        </p>

        <p>Best regards,<br>Technical Support Team</p>
    </body>
    </html>
    """

    return EmailContent(
        subject=subject,
        text_content=text_content,
        html_content=html_content,
    )
