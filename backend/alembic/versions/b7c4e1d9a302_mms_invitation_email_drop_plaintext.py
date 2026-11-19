"""mms invitation email: lookups by hash, drop plaintext (계획 23 M2)

킷 K3·K4 마이그레이션(48d0967a81f8 → 08755ebea028)과 매무새 M1(956f16a25c0f)을 합치면서
매무새 초대 이메일도 평문을 지웁니다. 되돌릴 수 없습니다 (downgrade 는 빈 평문 칸만 다시 만듦).
- mms_project_invitations: email_enc·email_hash NOT NULL
- 살아 있는 초대 하나만 (uq_mms_project_invitations_live) 을 (project_id, email) → (project_id, email_hash) 로
- 평문 email (+ ix_mms_project_invitations_email) 삭제
암호화 칸을 안 채운 초대가 있으면 멈춥니다 (M1 배포 뒤 pii-backfill 로 모두 채움, 2026-11-19 남은 행 0건 확인).
DB 백업에는 지운 평문이 백업 보관 기간 동안 남습니다.

Revision ID: b7c4e1d9a302
Revises: 956f16a25c0f, 08755ebea028
Create Date: 2026-11-19

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7c4e1d9a302"
down_revision: str | Sequence[str] | None = ("956f16a25c0f", "08755ebea028")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "mms_project_invitations"
LIVE = "uq_mms_project_invitations_live"
LIVE_WHERE = sa.text("accepted_at IS NULL AND revoked_at IS NULL")


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    unsynced = conn.execute(
        sa.text(f"SELECT count(*) FROM {TABLE} WHERE email_hash IS NULL OR email_enc IS NULL")
    ).scalar_one()
    if unsynced:
        raise RuntimeError(
            f"이메일 암호화 칸을 채우지 않은 초대가 {unsynced}건 있습니다. "
            "M1 코드(이 마이그레이션 전 버전)로 pii-backfill 을 먼저 실행한 뒤 다시 upgrade 하세요."
        )
    op.drop_index(LIVE, table_name=TABLE, postgresql_where=LIVE_WHERE)
    op.drop_index(op.f("ix_mms_project_invitations_email"), table_name=TABLE)
    op.drop_column(TABLE, "email")
    op.alter_column(TABLE, "email_enc", existing_type=postgresql.BYTEA(), nullable=False)
    op.alter_column(TABLE, "email_hash", existing_type=sa.VARCHAR(length=64), nullable=False)
    op.create_index(LIVE, TABLE, ["project_id", "email_hash"], unique=True, postgresql_where=LIVE_WHERE)


def downgrade() -> None:
    """Downgrade schema. 평문 칸만 다시 만들고 값은 되살리지 않습니다 (비어 있음, NOT NULL 없음)."""
    op.drop_index(LIVE, table_name=TABLE, postgresql_where=LIVE_WHERE)
    op.alter_column(TABLE, "email_hash", existing_type=sa.VARCHAR(length=64), nullable=True)
    op.alter_column(TABLE, "email_enc", existing_type=postgresql.BYTEA(), nullable=True)
    op.add_column(TABLE, sa.Column("email", sa.VARCHAR(length=255), nullable=True))
    op.create_index(op.f("ix_mms_project_invitations_email"), TABLE, ["email"], unique=False)
    op.create_index(LIVE, TABLE, ["project_id", "email"], unique=True, postgresql_where=LIVE_WHERE)
