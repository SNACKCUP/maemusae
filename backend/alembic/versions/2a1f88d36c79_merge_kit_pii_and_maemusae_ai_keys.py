"""merge kit pii (계획 23) and maemusae ai keys

Revision ID: 2a1f88d36c79
Revises: c66e2c5db544, cfe9930b9cfa
Create Date: 2026-11-18 07:05:18.925499

- 킷 마이그레이션(cfe9930b9cfa, 계획 23 K2)과 매무새 마지막 마이그레이션(c66e2c5db544)을 잇기만 함 (DB 변경 없음)
- 킷 파일은 미어킷과 똑같이 두어 다음 킷 업그레이드 때 그대로 복사할 수 있게 함

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '2a1f88d36c79'
down_revision: str | Sequence[str] | None = ('c66e2c5db544', 'cfe9930b9cfa')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""


def downgrade() -> None:
    """Downgrade schema."""
