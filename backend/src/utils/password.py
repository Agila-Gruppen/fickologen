import secrets

import bcrypt

# No 0/O or 1/I/L, so a code copied by hand is hard to get wrong.
RECOVERY_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def hash_password(password: str) -> str:
    """
    Hash a plain text password using bcrypt.

    Args:
        password: Plain text password to hash

    Returns:
        Hashed password string
    """
    # Convert password to bytes and hash it
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    # Return as string for database storage
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain text password against a hashed password.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to compare against

    Returns:
        True if the password matches, False otherwise
    """
    password_bytes = plain_password.encode('utf-8')
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def generate_recovery_code() -> str:
    """
    Generate a one-time recovery code, e.g. "K7QM-3XHP-W9RT-B2NV".

    Returns:
        The code in plain text. Store only its hash (hash_password).
    """
    chars = "".join(secrets.choice(RECOVERY_CODE_ALPHABET) for _ in range(16))
    return "-".join(chars[i:i + 4] for i in range(0, 16, 4))


def normalize_recovery_code(code: str) -> str:
    """
    Normalize a recovery code typed by a user: uppercase, spaces and
    dashes removed, then grouped the same way as generate_recovery_code.
    """
    chars = "".join(c for c in code.upper() if c.isalnum())
    return "-".join(chars[i:i + 4] for i in range(0, len(chars), 4))
