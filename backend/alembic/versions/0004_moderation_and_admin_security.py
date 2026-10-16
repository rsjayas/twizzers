"""moderation and admin security

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-16 15:50:40.850453

"""
from alembic import op
import sqlalchemy as sa


revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('reports',
    sa.Column('id', sa.UUID(as_uuid=False), nullable=False),
    sa.Column('creation_id', sa.UUID(as_uuid=False), nullable=False),
    sa.Column('reason', sa.String(), nullable=False),
    sa.Column('details', sa.String(), nullable=True),
    sa.Column('reporter_hash', sa.String(), nullable=True),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('handled_by', sa.String(), nullable=True),
    sa.Column('handled_at', sa.DateTime(), nullable=True),
    sa.Column('resolution_note', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['creation_id'], ['creations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_reports_creation_id'), 'reports', ['creation_id'], unique=False)
    op.create_index(op.f('ix_reports_status'), 'reports', ['status'], unique=False)
    op.add_column('admin_users', sa.Column('totp_secret', sa.String(), nullable=True))
    op.add_column('admin_users', sa.Column('totp_enabled', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('users', sa.Column('is_blocked', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('users', sa.Column('blocked_reason', sa.String(), nullable=True))
    op.add_column('users', sa.Column('deleted_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'deleted_at')
    op.drop_column('users', 'blocked_reason')
    op.drop_column('users', 'is_blocked')
    op.drop_column('admin_users', 'totp_enabled')
    op.drop_column('admin_users', 'totp_secret')
    op.drop_index(op.f('ix_reports_status'), table_name='reports')
    op.drop_index(op.f('ix_reports_creation_id'), table_name='reports')
    op.drop_table('reports')
