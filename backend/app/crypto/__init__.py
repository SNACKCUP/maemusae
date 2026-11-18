"""개인정보 암호화 공통 모듈 (core 만 import, 다른 공통 모듈과 독립).

이메일·전화번호·생년월일·주소처럼 다시 꺼내 써야 하는 개인정보를 양방향(AES-256-GCM)으로 암호화합니다.
비밀번호처럼 되돌릴 필요가 없는 값은 여기가 아니라 argon2 해시(app.core.security)를 씁니다.

    from app.crypto import EncryptedString, email_index, normalize_email

    # 모델: 저장할 때 암호화, 읽을 때 복호화
    email_enc: Mapped[str] = mapped_column(EncryptedString("users.email"))
    email_hash: Mapped[str] = mapped_column(String(64), unique=True)  # 검색·중복 확인용 지문

    # 저장: 암호문과 지문을 항상 같이 넣음
    user.email_enc = normalize_email(email)
    user.email_hash = email_index(email)

    # 찾기: 지문으로
    select(User).where(User.email_hash == email_index(입력값))

직접 쓸 때: encrypt(평문, aad) / decrypt(암호문, aad). aad 는 "테이블.컬럼" 처럼 값이 놓이는 자리 이름입니다.
키 설정은 app/crypto/config.py, 새 키는 uv run python -m app.crypto.keygen. 평문·키·암호문을 로그에 남기지 않습니다.
"""

from app.crypto.aead import decrypt, encrypt, key_version, needs_reencrypt, reencrypt
from app.crypto.blind_index import (
    blind_index,
    email_index,
    format_phone,
    normalize_email,
    normalize_phone,
    phone_index,
)
from app.crypto.columns import EncryptedDate, EncryptedString
from app.crypto.errors import CryptoNotConfiguredError, DecryptError, InvalidPhoneError

__all__ = [
    "CryptoNotConfiguredError",
    "DecryptError",
    "EncryptedDate",
    "EncryptedString",
    "InvalidPhoneError",
    "blind_index",
    "decrypt",
    "email_index",
    "encrypt",
    "format_phone",
    "key_version",
    "needs_reencrypt",
    "normalize_email",
    "normalize_phone",
    "phone_index",
    "reencrypt",
]
