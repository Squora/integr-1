"""Initial migration

Revision ID: 001
Revises: 
Create Date: 2025-10-14 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)

    op.create_table(
        'authors',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('birth_year', sa.Integer(), nullable=True),
        sa.Column('country', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_authors_id'), 'authors', ['id'], unique=False)

    op.create_table(
        'books_v1',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('author', sa.String(length=255), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('isbn', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_books_v1_id'), 'books_v1', ['id'], unique=False)
    op.create_index(op.f('ix_books_v1_isbn'), 'books_v1', ['isbn'], unique=True)

    op.create_table(
        'books_v2',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('isbn', sa.String(length=20), nullable=False),
        sa.Column('pages', sa.Integer(), nullable=True),
        sa.Column('genre', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['author_id'], ['authors.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_books_v2_id'), 'books_v2', ['id'], unique=False)
    op.create_index(op.f('ix_books_v2_isbn'), 'books_v2', ['isbn'], unique=True)

    op.create_table(
        'idempotency_keys',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=False),
        sa.Column('response_data', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_idempotency_keys_id'), 'idempotency_keys', ['id'], unique=False)
    op.create_index(op.f('ix_idempotency_keys_key'), 'idempotency_keys', ['key'], unique=True)

    op.create_table(
        'rate_limits',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('client_ip', sa.String(length=50), nullable=False),
        sa.Column('request_time', sa.DateTime(), nullable=True),
        sa.Column('endpoint', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_rate_limits_id'), 'rate_limits', ['id'], unique=False)
    op.create_index(op.f('ix_rate_limits_client_ip'), 'rate_limits', ['client_ip'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_rate_limits_client_ip'), table_name='rate_limits')
    op.drop_index(op.f('ix_rate_limits_id'), table_name='rate_limits')
    op.drop_table('rate_limits')
    
    op.drop_index(op.f('ix_idempotency_keys_key'), table_name='idempotency_keys')
    op.drop_index(op.f('ix_idempotency_keys_id'), table_name='idempotency_keys')
    op.drop_table('idempotency_keys')
    
    op.drop_index(op.f('ix_books_v2_isbn'), table_name='books_v2')
    op.drop_index(op.f('ix_books_v2_id'), table_name='books_v2')
    op.drop_table('books_v2')
    
    op.drop_index(op.f('ix_books_v1_isbn'), table_name='books_v1')
    op.drop_index(op.f('ix_books_v1_id'), table_name='books_v1')
    op.drop_table('books_v1')
    
    op.drop_index(op.f('ix_authors_id'), table_name='authors')
    op.drop_table('authors')
    
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_table('users')
