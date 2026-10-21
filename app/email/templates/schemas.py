from dataclasses import dataclass


@dataclass(frozen=True)
class EmailContent:
    subject: str
    text_content: str
    html_content: str | None = None
