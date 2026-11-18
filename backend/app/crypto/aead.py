"""양방향 암호화 (AES-256-GCM).

암호문 형식 (DB 에는 bytea 로 저장):

    [키 버전 1바이트][nonce 12바이트][암호문 + 인증 태그 16바이트]

- nonce 는 매번 무작위라 같은 값도 암호문이 매번 다릅니다. 그래서 암호문으로는 검색할 수 없고, 찾을 값은 지문(blind_index)을 씁니다.
- 인증 태그 덕분에 암호문이 한 바이트라도 바뀌면 풀 때 실패합니다 (변조 감지).
- aad(함께 묶는 꼬리표, 예: "users.phone")가 다르면 풀리지 않습니다. 다른 칸의 암호문을 옮겨 붙이는 바꿔치기를 막습니다.
"""

import logging
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.crypto.errors import DecryptError
from app.crypto.keys import load_keyring

logger = logging.getLogger(__name__)

NONCE_BYTES = 12
TAG_BYTES = 16
HEADER_BYTES = 1 + NONCE_BYTES
OVERHEAD_BYTES = HEADER_BYTES + TAG_BYTES  # 원문보다 29바이트 길어짐


def encrypt(plaintext: str, aad: str) -> bytes:
    """문자열을 지금 활성 키로 암호화합니다."""
    keyring = load_keyring()
    nonce = os.urandom(NONCE_BYTES)
    body = AESGCM(keyring.active_key).encrypt(nonce, plaintext.encode("utf-8"), aad.encode("utf-8"))
    return bytes([keyring.active_version]) + nonce + body


def key_version(blob: bytes) -> int:
    """암호문을 만든 키 버전 (키 교체 때 남은 행 확인용)"""
    if len(blob) < OVERHEAD_BYTES:
        raise DecryptError()
    return blob[0]


def decrypt(blob: bytes, aad: str) -> str:
    """암호문을 풉니다. 실패하면 500 PII_DECRYPT_FAILED. 로그에는 aad·키 버전·이유만 남깁니다 (값 없음)."""
    blob = bytes(blob)  # psycopg 가 memoryview 로 줄 때가 있음
    if len(blob) < OVERHEAD_BYTES:
        logger.error("개인정보 복호화 실패 aad=%s reason=too_short", aad)
        raise DecryptError()
    version = blob[0]
    keyring = load_keyring()
    key = keyring.encryption_keys.get(version)
    if key is None:
        logger.error("개인정보 복호화 실패 aad=%s key_version=%s reason=unknown_key_version", aad, version)
        raise DecryptError()
    nonce, body = blob[1:HEADER_BYTES], blob[HEADER_BYTES:]
    try:
        plain = AESGCM(key).decrypt(nonce, body, aad.encode("utf-8"))
    except InvalidTag:
        logger.error("개인정보 복호화 실패 aad=%s key_version=%s reason=invalid_tag", aad, version)
        raise DecryptError() from None
    return plain.decode("utf-8")


def needs_reencrypt(blob: bytes) -> bool:
    """활성 키가 아닌 옛 키로 만든 암호문인지"""
    return key_version(bytes(blob)) != load_keyring().active_version


def reencrypt(blob: bytes, aad: str) -> bytes:
    """옛 키 암호문을 활성 키로 다시 암호화합니다 (키 교체 명령에서 씀). 이미 활성 키면 그대로 돌려줍니다."""
    blob = bytes(blob)
    if not needs_reencrypt(blob):
        return blob
    return encrypt(decrypt(blob, aad), aad)
