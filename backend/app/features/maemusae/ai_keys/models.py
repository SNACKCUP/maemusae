"""개인 AI 키 테이블.

    users ──o mms_user_ai_keys      회원 한 명에 키 하나 (공급자는 지금 openai 만)

provider 는 코드가 흐름을 바꾸는 값이라 공통코드가 아니라 CHECK 로 둡니다.
"""

from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.models import TimestampMixin

OPENAI = "openai"
PROVIDERS = (OPENAI,)


class UserAiKey(TimestampMixin, Base):
    __tablename__ = "mms_user_ai_keys"
    __table_args__ = (CheckConstraint("provider IN ('openai')", name="ck_mms_user_ai_keys_provider"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    provider: Mapped[str] = mapped_column(String(20))
    encrypted_key: Mapped[str] = mapped_column(Text)  # Fernet 토큰 (MMS_AI_KEY_ENCRYPTION_KEY 로 암호화)
    key_hint: Mapped[str] = mapped_column(String(8))  # 화면에 보일 끝 4자리
