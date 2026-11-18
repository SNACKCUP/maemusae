"""새 키 만들기: uv run python -m app.crypto.keygen [버전]

화면에만 출력합니다 (로그·파일에 남기지 않음). 나온 두 줄을 .env 또는 서버 환경변수에 넣고,
비밀번호 관리자처럼 DB 백업과 다른 안전한 곳에 따로 보관하세요. 암호화 키를 잃으면 암호화한 정보를 되살릴 수 없습니다.

키 교체 때는 버전을 올려 만든 키를 PII_ENCRYPTION_KEYS 뒤에 이어 붙이고(쉼표), PII_ENCRYPTION_ACTIVE_KEY 를 새 버전으로 바꿉니다.
"""

import base64
import secrets
import sys

from app.crypto.keys import KEY_BYTES, MAX_KEY_VERSION, MIN_HMAC_KEY_BYTES


def _new_key(size: int) -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(size)).decode()


def main(argv: list[str]) -> int:
    version = int(argv[0]) if argv else 1
    if not 1 <= version <= MAX_KEY_VERSION:
        print(f"버전은 1~{MAX_KEY_VERSION} 사이로 주세요", file=sys.stderr)
        return 2
    print(f"PII_ENCRYPTION_KEYS={version}:{_new_key(KEY_BYTES)}")
    if version == 1:
        print(f"PII_HMAC_KEY={_new_key(MIN_HMAC_KEY_BYTES)}")
    else:
        print("# PII_HMAC_KEY 는 그대로 두세요 (바꾸면 모든 지문을 다시 계산해야 함)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
