import os


def admin_usernames() -> set[str]:
    raw = os.environ.get("ADMIN_USERNAMES", "")
    return {name.strip() for name in raw.split(",") if name.strip()}


def is_admin_username(username: str) -> bool:
    return username in admin_usernames()