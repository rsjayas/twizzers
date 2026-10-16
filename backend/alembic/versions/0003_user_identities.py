"""user identities

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-16 15:37:13.637956

"""
from alembic import op
import sqlalchemy as sa


revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('user_identities',
    sa.Column('id', sa.UUID(as_uuid=False), nullable=False),
    sa.Column('user_id', sa.UUID(as_uuid=False), nullable=False),
    sa.Column('firebase_uid', sa.String(), nullable=False),
    sa.Column('provider', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_identities_firebase_uid'), 'user_identities', ['firebase_uid'], unique=True)
    op.create_index(op.f('ix_user_identities_user_id'), 'user_identities', ['user_id'], unique=False)
    # Keep existing logins working: every user's Firebase account becomes an identity.
    op.execute(
        "INSERT INTO user_identities (id, user_id, firebase_uid, provider, created_at) "
        "SELECT gen_random_uuid(), id, firebase_uid, COALESCE(NULLIF(auth_provider, 'firebase'), 'other'), now() "
        "FROM users WHERE firebase_uid IS NOT NULL"
    )
    op.drop_index('ix_users_firebase_uid', table_name='users')
    op.drop_column('users', 'firebase_uid')


def downgrade() -> None:
    op.add_column('users', sa.Column('firebase_uid', sa.VARCHAR(), autoincrement=False, nullable=True))
    op.create_index('ix_users_firebase_uid', 'users', ['firebase_uid'], unique=True)
    op.execute(
        "UPDATE users SET firebase_uid = (SELECT firebase_uid FROM user_identities i "
        "WHERE i.user_id = users.id ORDER BY created_at LIMIT 1)"
    )
    op.drop_index(op.f('ix_user_identities_user_id'), table_name='user_identities')
    op.drop_index(op.f('ix_user_identities_firebase_uid'), table_name='user_identities')
    op.drop_table('user_identities')
