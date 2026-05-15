from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

try:
    from .profile_schema import ProfileValidationError, validate_profile
except ImportError:
    from profile_schema import ProfileValidationError, validate_profile


ENVELOPE_PRODUCT = "PROXY_GATEWAY_PROFILE"
ENVELOPE_VERSION = 1
ALGORITHM = "AES-256-GCM"
KDF = "PBKDF2-HMAC-SHA256"
KDF_ITERATIONS = 390_000
SALT_BYTES = 16
NONCE_BYTES = 12
AAD = b"PROXY_GATEWAY_PROFILE:v1"


class ProfileCryptoError(ValueError):
    pass


def encrypt_profile(profile: dict[str, Any], passphrase: str) -> dict[str, Any]:
    if not passphrase:
        raise ProfileCryptoError("passphrase is required")
    validated = validate_profile(profile)
    salt = os.urandom(SALT_BYTES)
    nonce = os.urandom(NONCE_BYTES)
    key = _derive_key(passphrase, salt)
    plaintext = _canonical_json(validated).encode("utf-8")
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, AAD)
    return {
        "product": ENVELOPE_PRODUCT,
        "version": ENVELOPE_VERSION,
        "algorithm": ALGORITHM,
        "kdf": KDF,
        "iterations": KDF_ITERATIONS,
        "salt": _b64encode(salt),
        "nonce": _b64encode(nonce),
        "ciphertext": _b64encode(ciphertext),
    }


def decrypt_profile(envelope: dict[str, Any], passphrase: str) -> dict[str, Any]:
    if not passphrase:
        raise ProfileCryptoError("passphrase is required")
    _validate_envelope(envelope)
    try:
        salt = _b64decode(envelope["salt"])
        nonce = _b64decode(envelope["nonce"])
        ciphertext = _b64decode(envelope["ciphertext"])
    except (KeyError, ValueError) as error:
        raise ProfileCryptoError("encrypted profile is malformed") from error

    key = _derive_key(passphrase, salt)
    try:
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, AAD)
    except InvalidTag as error:
        raise ProfileCryptoError("profile passphrase is invalid or profile is corrupted") from error

    try:
        profile = json.loads(plaintext.decode("utf-8"))
        return validate_profile(profile)
    except (UnicodeDecodeError, json.JSONDecodeError, ProfileValidationError) as error:
        raise ProfileCryptoError(f"profile validation failed: {error}") from error


def write_encrypted_profile(profile: dict[str, Any], path: str | Path, passphrase: str) -> dict[str, Any]:
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    envelope = encrypt_profile(profile, passphrase)
    target.write_text(json.dumps(envelope, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    target.chmod(0o600)
    validated = validate_profile(profile)
    return {
        "ok": True,
        "path": str(target),
        "summary": profile_summary(validated),
        "profileDigest": profile_digest(validated),
    }


def read_encrypted_profile(path: str | Path, passphrase: str) -> dict[str, Any]:
    try:
        envelope = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ProfileCryptoError("encrypted profile is missing") from error
    except json.JSONDecodeError as error:
        raise ProfileCryptoError("encrypted profile is not valid JSON") from error
    return decrypt_profile(envelope, passphrase)


def encrypted_profile_status(path: str | Path) -> dict[str, Any]:
    target = Path(path).expanduser()
    if not target.exists():
        return {
            "present": False,
            "state": "missing",
            "path": str(target),
            "errors": ["encrypted profile is missing"],
        }
    try:
        envelope = json.loads(target.read_text(encoding="utf-8"))
        _validate_envelope(envelope)
    except json.JSONDecodeError:
        return {
            "present": True,
            "state": "invalid_json",
            "path": str(target),
            "errors": ["encrypted profile is not valid JSON"],
        }
    except ProfileCryptoError as error:
        return {
            "present": True,
            "state": "invalid_envelope",
            "path": str(target),
            "errors": [str(error)],
        }
    return {
        "present": True,
        "state": "encrypted_profile_present",
        "path": str(target),
        "errors": [],
    }


def copy_encrypted_profile(source: str | Path, target: str | Path) -> dict[str, Any]:
    source_path = Path(source).expanduser()
    target_path = Path(target).expanduser()
    _assert_encrypted_profile_destination(target_path)
    status = encrypted_profile_status(source_path)
    if not status["present"]:
        raise ProfileCryptoError("encrypted profile source is missing")
    if status["state"] != "encrypted_profile_present":
        raise ProfileCryptoError("; ".join(status["errors"]) or "encrypted profile source is invalid")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
    target_path.chmod(0o600)
    return {
        "ok": True,
        "source": str(source_path),
        "path": str(target_path),
        "state": "copied",
    }


def profile_summary(profile: dict[str, Any]) -> dict[str, Any]:
    routes = profile.get("routes", {})
    split_rules = profile.get("splitRules", {})
    return {
        "name": profile.get("name", "linux-lan-gateway"),
        "routeIds": sorted(routes),
        "routeCount": len(routes),
        "splitPolicy": split_rules.get("policy", "unknown"),
        "privacy": profile.get("privacy", {}),
    }


def profile_digest(profile: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(validate_profile(profile)).encode("utf-8")).hexdigest()


def _validate_envelope(envelope: dict[str, Any]) -> None:
    if not isinstance(envelope, dict):
        raise ProfileCryptoError("encrypted profile envelope must be an object")
    expected = {
        "product": ENVELOPE_PRODUCT,
        "version": ENVELOPE_VERSION,
        "algorithm": ALGORITHM,
        "kdf": KDF,
        "iterations": KDF_ITERATIONS,
    }
    for key, value in expected.items():
        if envelope.get(key) != value:
            raise ProfileCryptoError(f"encrypted profile {key} mismatch")


def _assert_encrypted_profile_destination(path: Path) -> None:
    if path.name != "profile.json.enc" and not path.name.endswith(".json.enc"):
        raise ProfileCryptoError("encrypted profile destination must end with .json.enc")


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    return PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=KDF_ITERATIONS,
    ).derive(passphrase.encode("utf-8"))


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value.encode("ascii"))
