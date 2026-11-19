"""pii encrypted columns

Revision ID: cfe9930b9cfa
Revises: 72d61ade7e67
Create Date: 2026-11-16 09:20:00.000000

- 계획 23 K2: 개인정보 암호화 칸 추가 (모두 nullable, 평문 칸은 그대로)
  - users: email_enc·phone_enc·birth_date_enc·postcode_enc·address_enc·address_detail_enc(bytea 암호문),
    email_hash·phone_hash(지문, 인덱스), phone_verified_at, birth_year(통계용 평문), pii_key_version
  - email_verifications.email_hash, social_accounts.email_enc
- 컬럼 추가만이라 이전 코드와도 같이 돌아감 (추가 먼저, 삭제는 나중). 기존 행 채우기는 마이그레이션이 아니라
  uv run python -m app.users.pii_backfill (키가 필요하고 건수가 많을 수 있어서)
- downgrade 는 추가한 칸만 삭제 (평문 칸이 남아 있어 잃는 데이터 없음)

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'cfe9930b9cfa'
down_revision: str | Sequence[str] | None = '72d61ade7e67'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('email_enc', sa.LargeBinary(), nullable=True))
    op.add_column('users', sa.Column('email_hash', sa.String(length=64), nullable=True))
    op.add_column('users', sa.Column('phone_enc', sa.LargeBinary(), nullable=True))
    op.add_column('users', sa.Column('phone_hash', sa.String(length=64), nullable=True))
    op.add_column('users', sa.Column('phone_verified_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('birth_date_enc', sa.LargeBinary(), nullable=True))
    op.add_column('users', sa.Column('birth_year', sa.SmallInteger(), nullable=True))
    op.add_column('users', sa.Column('postcode_enc', sa.LargeBinary(), nullable=True))
    op.add_column('users', sa.Column('address_enc', sa.LargeBinary(), nullable=True))
    op.add_column('users', sa.Column('address_detail_enc', sa.LargeBinary(), nullable=True))
    op.add_column('users', sa.Column('pii_key_version', sa.SmallInteger(), nullable=True))
    op.create_index(op.f('ix_users_email_hash'), 'users', ['email_hash'], unique=False)
    op.create_index(op.f('ix_users_phone_hash'), 'users', ['phone_hash'], unique=False)
    op.add_column('email_verifications', sa.Column('email_hash', sa.String(length=64), nullable=True))
    op.create_index(op.f('ix_email_verifications_email_hash'), 'email_verifications', ['email_hash'], unique=False)
    op.add_column('social_accounts', sa.Column('email_enc', sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('social_accounts', 'email_enc')
    op.drop_index(op.f('ix_email_verifications_email_hash'), table_name='email_verifications')
    op.drop_column('email_verifications', 'email_hash')
    op.drop_index(op.f('ix_users_phone_hash'), table_name='users')
    op.drop_index(op.f('ix_users_email_hash'), table_name='users')
    for name in (
        'pii_key_version', 'address_detail_enc', 'address_enc', 'postcode_enc', 'birth_year',
        'birth_date_enc', 'phone_verified_at', 'phone_hash', 'phone_enc', 'email_hash', 'email_enc',
    ):
        op.drop_column('users', name)
