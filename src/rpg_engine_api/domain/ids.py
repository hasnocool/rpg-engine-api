import re
from uuid import uuid4

_CONTENT_KEY = re.compile(r"^[a-z0-9][a-z0-9_.-]*:[a-z0-9][a-z0-9_./-]*$")


def new_id(prefix: str) -> str:
    if not prefix or not prefix.replace("_", "").isalnum():
        raise ValueError("ID prefix must be alphanumeric/underscore")
    return f"{prefix}_{uuid4().hex}"


def validate_content_key(value: str) -> str:
    if not _CONTENT_KEY.fullmatch(value):
        raise ValueError("content key must be namespace:path using lowercase stable characters")
    return value
