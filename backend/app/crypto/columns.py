"""SQLAlchemy 컬럼 타입: 저장할 때 암호화, 읽을 때 복호화 (JPA 의 @Convert(converter=...) 와 같은 역할).

    from app.crypto import EncryptedString, EncryptedDate

    phone_enc: Mapped[str | None] = mapped_column(EncryptedString("users.phone"))
    birth_date_enc: Mapped[date | None] = mapped_column(EncryptedDate("users.birth_date"))

괄호 안 문자열은 aad 입니다 (보통 "테이블.원래 컬럼 이름"). 한 번 정하면 바꾸지 않습니다 (바꾸면 옛 값이 안 풀림).
DB 타입은 bytea 입니다. 암호문은 매번 달라 WHERE·ORDER BY 에 쓸 수 없습니다. 찾을 값은 blind_index 지문 칸을 따로 둡니다.
"""

from datetime import date

from sqlalchemy import LargeBinary
from sqlalchemy.sql import operators
from sqlalchemy.types import TypeDecorator

from app.crypto.aead import decrypt, encrypt

# IS NULL / IS NOT NULL 만 허용합니다. == · ilike · 정렬은 암호문이 매번 달라 조용히 틀린 결과가 나오므로 막습니다.
_ALLOWED_OPS = {operators.is_, operators.is_not}


class _NoCompare(TypeDecorator.Comparator):
    def operate(self, op, *other, **kwargs):
        if op not in _ALLOWED_OPS:
            raise TypeError("암호화 칸은 WHERE·정렬에 쓸 수 없습니다. 지문 칸(email_hash·phone_hash)으로 찾으세요.")
        return super().operate(op, *other, **kwargs)

    def reverse_operate(self, op, other, **kwargs):
        if op not in _ALLOWED_OPS:
            raise TypeError("암호화 칸은 WHERE·정렬에 쓸 수 없습니다. 지문 칸(email_hash·phone_hash)으로 찾으세요.")
        return super().reverse_operate(op, other, **kwargs)


class EncryptedString(TypeDecorator[str]):
    impl = LargeBinary
    cache_ok = True
    comparator_factory = _NoCompare

    def __init__(self, aad: str) -> None:
        super().__init__()
        self.aad = aad

    def process_bind_param(self, value: str | None, dialect) -> bytes | None:
        if value is None:
            return None
        return encrypt(value, self.aad)

    def process_result_value(self, value: bytes | None, dialect) -> str | None:
        if value is None:
            return None
        return decrypt(value, self.aad)


class EncryptedDate(TypeDecorator[date]):
    """날짜를 YYYY-MM-DD 문자열로 바꿔 암호화합니다."""

    impl = LargeBinary
    cache_ok = True
    comparator_factory = _NoCompare

    def __init__(self, aad: str) -> None:
        super().__init__()
        self.aad = aad

    def process_bind_param(self, value: date | None, dialect) -> bytes | None:
        if value is None:
            return None
        return encrypt(value.isoformat(), self.aad)

    def process_result_value(self, value: bytes | None, dialect) -> date | None:
        if value is None:
            return None
        return date.fromisoformat(decrypt(value, self.aad))
