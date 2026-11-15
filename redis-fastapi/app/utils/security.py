import hashlib
import secrets


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        100_000
    )
    return f"{salt}${key.hex()}"


def verify_password(plain_password: str, hashed_password: str | None) -> bool:
    if not hashed_password or "$" not in hashed_password:
        return False
    try:
        salt_hex, key_hex = hashed_password.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        new_key = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt,
            100_000
        )
        return secrets.compare_digest(new_key.hex(), key_hex)
    except Exception:
        return False
