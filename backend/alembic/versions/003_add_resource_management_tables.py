"""Add resource management tables

Revision ID: 003_add_resource_management_tables
Revises: 002_remove_split_audio_fields
Create Date: 2025-01-10 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None

def upgrade():
    # 创建resource_tags表
    op.create_table('resource_tags',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('tag_type', sa.String(length=50), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_resource_tags_id'), 'resource_tags', ['id'], unique=False)
    op.create_index(op.f('ix_resource_tags_name'), 'resource_tags', ['name'], unique=True)
    op.create_index(op.f('ix_resource_tags_tag_type'), 'resource_tags', ['tag_type'], unique=False)
    op.create_index(op.f('ix_resource_tags_is_active'), 'resource_tags', ['is_active'], unique=False)
    
    # 创建resources表
    op.create_table('resources',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('file_size', sa.Float(), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=False),
        sa.Column('file_type', sa.String(length=50), nullable=False),
        sa.Column('duration', sa.Float(), nullable=True),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('description', sa.String(length=1000), nullable=True),
        sa.Column('is_public', sa.Boolean(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('download_count', sa.Integer(), nullable=False),
        sa.Column('view_count', sa.Integer(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_resources_filename'), 'resources', ['filename'], unique=False)
    op.create_index(op.f('ix_resources_file_path'), 'resources', ['file_path'], unique=True)
    op.create_index(op.f('ix_resources_file_type'), 'resources', ['file_type'], unique=False)
    op.create_index(op.f('ix_resources_is_public'), 'resources', ['is_public'], unique=False)
    op.create_index(op.f('ix_resources_is_active'), 'resources', ['is_active'], unique=False)
    op.create_index(op.f('ix_resources_created_by'), 'resources', ['created_by'], unique=False)
    
    # 创建resource_tags_mapping表（多对多关系）
    op.create_table('resource_tags_mapping',
        sa.Column('resource_id', sa.Integer(), nullable=False),
        sa.Column('tag_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['resource_id'], ['resources.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tag_id'], ['resource_tags.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('resource_id', 'tag_id')
    )

def downgrade():
    # 删除resource_tags_mapping表
    op.drop_table('resource_tags_mapping')
    
    # 删除resources表
    op.drop_table('resources')
    
    # 删除resource_tags表
    op.drop_table('resource_tags')