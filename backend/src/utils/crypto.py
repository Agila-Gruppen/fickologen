import os
from functools import lru_cache
from typing import Optional

from cryptography.fernet import Fernet, MultiFernet
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator


@lru_cache(maxsize=1)
def _fernet() -> MultiFernet:
    """
    Builds the cipher from DATA_ENCRYPTION_KEY.

    The variable holds one or more comma-separated Fernet keys. New data is
    always encrypted with the first key; all keys are tried when decrypting,
    so a key can be rotated by putting the new one first and keeping the old
    one until everything has been re-encrypted.

    Raises:
        RuntimeError: if DATA_ENCRYPTION_KEY is not set
    """
    raw = os.environ.get("DATA_ENCRYPTION_KEY", "")
    keys = [key.strip() for key in raw.split(",") if key.strip()]
    if not keys:
        raise RuntimeError(
            "DATA_ENCRYPTION_KEY is not set. Create one with: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return MultiFernet([Fernet(key.encode()) for key in keys])


def encrypt(value: str) -> str:
    """Encrypts a string to a URL-safe base64 Fernet token."""
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    """
    Decrypts a Fernet token made by encrypt().

    Raises:
        cryptography.fernet.InvalidToken: if the token is not valid for any key
    """
    return _fernet().decrypt(token.encode("ascii")).decode("utf-8")


class EncryptedText(TypeDecorator):
    """
    A Text column that is encrypted at rest.

    Python code reads and writes plain strings; the database only ever sees
    the encrypted token. Because of that the column cannot be searched or
    sorted on in SQL - filter in Python after loading instead.
    """
    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Optional[str], dialect) -> Optional[str]:
        if value is None:
            return None
        return encrypt(value)

    def process_result_value(self, value: Optional[str], dialect) -> Optional[str]:
        if value is None:
            return None
        return decrypt(value)
