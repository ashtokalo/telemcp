"""Encrypted session storage for telemcp.

If the TELEMCP_PINCODE environment variable is set, the Telethon session string
is stored encrypted on disk.  Otherwise, the plain SQLite session is used.

Encryption : Fernet (AES-128-CBC + HMAC-SHA256)
Key derivation : PBKDF2-HMAC-SHA256, 200 000 iterations, random 16-byte salt
File format : JSON {"salt": "<hex>", "data": "<fernet_token>"}
"""
import base64
import hashlib
import json
import os
import sys

ENV_VAR = "TELEMCP_PINCODE"


def pin_is_set() -> bool:
    return bool(os.environ.get(ENV_VAR))


def get_pin() -> str:
    return os.environ.get(ENV_VAR, "")


def enc_path(session_file: str) -> str:
    """Return the path used for the encrypted session file."""
    return session_file + ".enc"


def _derive_key(pin: str, salt: bytes) -> bytes:
    dk = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, 200_000)
    return base64.urlsafe_b64encode(dk)


def save(session_string: str, path: str, pin: str) -> None:
    """Encrypt *session_string* with *pin* and write to *path* atomically."""
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        print(
            "[telemcp] 'cryptography' package is required for encrypted sessions: "
            "pip install cryptography",
            file=sys.stderr,
        )
        raise

    salt = os.urandom(16)
    key = _derive_key(pin, salt)
    token = Fernet(key).encrypt(session_string.encode("utf-8"))
    payload = {"salt": salt.hex(), "data": token.decode("ascii")}
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="ascii") as fp:
        json.dump(payload, fp)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def load(path: str, pin: str) -> str:
    """Decrypt and return the session string from *path*."""
    try:
        from cryptography.fernet import Fernet, InvalidToken
    except ImportError:
        print(
            "[telemcp] 'cryptography' package is required for encrypted sessions: "
            "pip install cryptography",
            file=sys.stderr,
        )
        raise

    with open(path, encoding="ascii") as fp:
        payload = json.load(fp)

    salt = bytes.fromhex(payload["salt"])
    key = _derive_key(pin, salt)
    try:
        return Fernet(key).decrypt(payload["data"].encode("ascii")).decode("utf-8")
    except InvalidToken:
        print(
            "[telemcp] Failed to decrypt session: wrong TELEMCP_PINCODE?",
            file=sys.stderr,
        )
        sys.exit(1)
