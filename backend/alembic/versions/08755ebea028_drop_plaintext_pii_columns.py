"""drop plaintext pii columns (계획 23 K4)

K3 부터 읽지 않던 옛 평문 개인정보 칸을 지웁니다. 되돌릴 수 없습니다 (downgrade 는 빈 칸만 다시 만듦).
- users: email, phone, postcode, address, address_detail, birth_date (+ ix_users_email)
- email_verifications: email (+ ix_email_verifications_email). 앞으로는 지문(email_hash)만 저장
- social_accounts: email
DB 백업에는 지운 평문이 백업 보관 기간 동안 남습니다.

Revision ID: 08755ebea028
Revises: 48d0967a81f8
Create Date: 2026-11-17

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "08755ebea028"
down_revision: str | Sequence[str] | None = "48d0967a81f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

USERS_PLAIN = ("email", "phone", "postcode", "address", "address_detail", "birth_date")


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index(op.f("ix_email_verifications_email"), table_name="email_verifications")
    op.drop_column("email_verifications", "email")
    op.drop_column("social_accounts", "email")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    for column in USERS_PLAIN:
        op.drop_column("users", column)


def downgrade() -> None:
    """Downgrade schema. 칸만 다시 만들고 값은 되살리지 않습니다 (모두 비어 있음, NOT NULL·UNIQUE 없음)."""
    op.add_column("users", sa.Column("email", sa.VARCHAR(length=255), nullable=True))
    op.add_column("users", sa.Column("phone", sa.VARCHAR(length=20), nullable=True))
    op.add_column("users", sa.Column("postcode", sa.VARCHAR(length=10), nullable=True))
    op.add_column("users", sa.Column("address", sa.VARCHAR(length=255), nullable=True))
    op.add_column("users", sa.Column("address_detail", sa.VARCHAR(length=255), nullable=True))
    op.add_column("users", sa.Column("birth_date", sa.DATE(), nullable=True))
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False)
    op.add_column("social_accounts", sa.Column("email", sa.VARCHAR(length=255), nullable=True))
    op.add_column("email_verifications", sa.Column("email", sa.VARCHAR(length=255), nullable=True))
    op.create_index(op.f("ix_email_verifications_email"), "email_verifications", ["email"], unique=False)
