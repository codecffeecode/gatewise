import re
from typing import Annotated

from pydantic import AfterValidator, Field

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(value: str) -> str:
    value = value.strip().lower()
    if not _EMAIL_RE.match(value):
        raise ValueError("Enter a valid email address")
    return value


Email = Annotated[str, Field(max_length=254), AfterValidator(normalize_email)]
Password = Annotated[str, Field(min_length=8, max_length=128)]
PersonName = Annotated[str, Field(min_length=1, max_length=120)]
