"""Security helpers scaffolded for later authentication work."""

import hashlib
import hmac
import secrets


def hash_password(password: str, *, iterations: int = 100_000) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    return f"{iterations}${salt}${digest.hex()}"


def verify_password(password: str, hashed_password: str) -> bool:
    iterations_text, salt, expected = hashed_password.split("$", maxsplit=2)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        int(iterations_text),
    )
    return hmac.compare_digest(digest.hex(), expected)
