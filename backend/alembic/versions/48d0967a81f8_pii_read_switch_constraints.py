"""pii read switch constraints (계획 23 K3)

읽기를 암호화 칸으로 옮기면서 제약을 바꿉니다.
- users: email_enc·email_hash·pii_key_version NOT NULL, email_hash 일반 인덱스 → UNIQUE (가입 중복을 지문으로 막음)
- email_verifications: email_hash NOT NULL. K2 이전에 만든 행(지문 없음)은 이미 만료된 인증번호라 지웁니다
  (인증번호 유효 시간은 분 단위, 키 없이 지문을 만들 수 없음)

옛 평문 칸(users.email UNIQUE 등)은 그대로 둡니다. 코드가 같은 값을 계속 쓰므로 K2 코드로 되돌릴 수 있고, K4 에서 지웁니다.
암호화 칸을 아직 안 채운 회원이 있으면 멈춥니다 → `uv run python -m app.users.pii_backfill` 실행 후 다시 upgrade.

Revision ID: 48d0967a81f8
Revises: cfe9930b9cfa
Create Date: 2026-11-17 02:06:59.802153

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "48d0967a81f8"
down_revision: str | Sequence[str] | None = "cfe9930b9cfa"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    unsynced = conn.execute(
        sa.text("SELECT count(*) FROM users WHERE email_hash IS NULL OR email_enc IS NULL OR pii_key_version IS NULL")
    ).scalar_one()
    if unsynced:
        raise RuntimeError(
            f"암호화 칸을 채우지 않은 회원이 {unsynced}명 있습니다. "
            "`uv run python -m app.users.pii_backfill` (Actions → pii-backfill) 를 먼저 실행한 뒤 다시 upgrade 하세요."
        )
    op.execute("DELETE FROM email_verifications WHERE email_hash IS NULL")

    op.alter_column("email_verifications", "email_hash", existing_type=sa.VARCHAR(length=64), nullable=False)
    op.alter_column("users", "email_enc", existing_type=postgresql.BYTEA(), nullable=False)
    op.alter_column("users", "email_hash", existing_type=sa.VARCHAR(length=64), nullable=False)
    op.alter_column("users", "pii_key_version", existing_type=sa.SMALLINT(), nullable=False)
    op.drop_index(op.f("ix_users_email_hash"), table_name="users")
    op.create_unique_constraint("users_email_hash_key", "users", ["email_hash"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("users_email_hash_key", "users", type_="unique")
    op.create_index(op.f("ix_users_email_hash"), "users", ["email_hash"], unique=False)
    op.alter_column("users", "pii_key_version", existing_type=sa.SMALLINT(), nullable=True)
    op.alter_column("users", "email_hash", existing_type=sa.VARCHAR(length=64), nullable=True)
    op.alter_column("users", "email_enc", existing_type=postgresql.BYTEA(), nullable=True)
    op.alter_column("email_verifications", "email_hash", existing_type=sa.VARCHAR(length=64), nullable=True)
