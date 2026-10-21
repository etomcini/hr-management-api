from app.email.templates.schemas import EmailContent


def build_employee_welcome_email() -> EmailContent:
    subject = "Welcome to Our Company"

    text_content = (
        "Hello,\n\n"
        "Welcome to our company! We're excited to have you on board.\n\n"
        "If you have any questions, feel free to reach out to your manager or the HR team.\n\n"
        "Best regards,\n"
        "HR Team"
    )

    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <body>
        <h2>Welcome to Our Company</h2>

        <p>Hello,</p>

        <p>
            Welcome to our company! We're excited to have you on board.
        </p>

        <p>
            If you have any questions, feel free to reach out to your manager or the HR team.
        </p>

        <p>Best regards,<br>HR Team</p>
    </body>
    </html>
    """

    return EmailContent(
        subject=subject,
        text_content=text_content,
        html_content=html_content,
    )
