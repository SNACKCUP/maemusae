"""키 읽기. 설정 문자열을 검사해 바이트 키로 바꿉니다. 오류 문구에는 키 값을 넣지 않습니다."""

import base64
import binascii
from dataclasses import dataclass

from app.crypto.config import CryptoSettings, crypto_settings
from app.crypto.errors import CryptoNotConfiguredError

KEY_BYTES = 32  # AES-256
MIN_HMAC_KEY_BYTES = 32
MAX_KEY_VERSION = 255  # 암호문 맨 앞 1바이트에 버전을 적음


@dataclass(frozen=True)
class Keyring:
    encryption_keys: dict[int, bytes]  # 버전 → 키
    active_version: int
    hmac_key: bytes

    @property
    def active_key(self) -> bytes:
        return self.encryption_keys[self.active_version]


def _b64decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode())


def _parse_encryption_keys(raw: str) -> dict[int, bytes]:
    keys: dict[int, bytes] = {}
    for part in (p.strip() for p in raw.split(",")):
        if not part:
            continue
        version_text, sep, key_text = part.partition(":")
        if not sep or not version_text.strip().isdigit():
            raise ValueError("PII_ENCRYPTION_KEYS: 각 항목은 '버전:키' 형식이어야 합니다 (예: 1:base64...)")
        version = int(version_text)
        if not 1 <= version <= MAX_KEY_VERSION:
            raise ValueError(f"PII_ENCRYPTION_KEYS: 버전은 1~{MAX_KEY_VERSION} 사이여야 합니다")
        if version in keys:
            raise ValueError(f"PII_ENCRYPTION_KEYS: 버전 {version} 이 두 번 있습니다")
        try:
            key = _b64decode(key_text.strip())
        except (binascii.Error, ValueError) as e:
            raise ValueError(f"PII_ENCRYPTION_KEYS: 버전 {version} 키가 base64 형식이 아닙니다") from e
        if len(key) != KEY_BYTES:
            raise ValueError(f"PII_ENCRYPTION_KEYS: 버전 {version} 키는 {KEY_BYTES}바이트여야 합니다 (keygen 으로 만드세요)")
        keys[version] = key
    if not keys:
        raise ValueError("PII_ENCRYPTION_KEYS: 비어 있습니다 (uv run python -m app.crypto.keygen 으로 만드세요)")
    return keys


def _parse_hmac_key(raw: str) -> bytes:
    if not raw.strip():
        raise ValueError("PII_HMAC_KEY: 비어 있습니다 (uv run python -m app.crypto.keygen 으로 만드세요)")
    try:
        key = _b64decode(raw.strip())
    except (binascii.Error, ValueError) as e:
        raise ValueError("PII_HMAC_KEY: base64 형식이 아닙니다") from e
    if len(key) < MIN_HMAC_KEY_BYTES:
        raise ValueError(f"PII_HMAC_KEY: {MIN_HMAC_KEY_BYTES}바이트 이상이어야 합니다")
    return key


def build_keyring(s: CryptoSettings) -> Keyring:
    """설정을 검사해 Keyring 을 만듭니다. 틀리면 ValueError(무엇이 틀렸는지만, 키 값 없음)."""
    keys = _parse_encryption_keys(s.pii_encryption_keys.get_secret_value())
    hmac_key = _parse_hmac_key(s.pii_hmac_key.get_secret_value())
    active = s.pii_encryption_active_key if s.pii_encryption_active_key is not None else max(keys)
    if active not in keys:
        raise ValueError(f"PII_ENCRYPTION_ACTIVE_KEY: 버전 {active} 이 PII_ENCRYPTION_KEYS 에 없습니다")
    if any(hmac_key == k for k in keys.values()):
        raise ValueError("PII_HMAC_KEY: 암호화 키와 다른 값을 쓰세요 (한 키가 새면 둘 다 위험)")
    return Keyring(encryption_keys=keys, active_version=active, hmac_key=hmac_key)


def key_problems(s: CryptoSettings) -> list[str]:
    """설정 검사 결과 (운영 시작 검사용). 문제가 없으면 빈 목록"""
    try:
        build_keyring(s)
    except ValueError as e:
        return [str(e)]
    return []


def load_keyring() -> Keyring:
    """지금 설정의 Keyring. 설정이 틀리면 503 PII_CRYPTO_NOT_CONFIGURED.

    매번 설정을 읽어 만듭니다 (base64 몇 개를 푸는 정도라 가볍고, 테스트에서 설정을 바꿔도 바로 반영).
    """
    try:
        return build_keyring(crypto_settings)
    except ValueError as e:
        raise CryptoNotConfiguredError() from e
