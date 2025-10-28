"""Add Jianying fields to video_slice table

Revision ID: 006_add_jianying_fields_to_video_slice
Revises: 37972a95e74c
Create Date: 2025-10-26 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '006'
down_revision = '37972a95e74c'
branch_labels = None
depends_on = None


def upgrade():
    # Add Jianying fields to video_slices table
    op.add_column('video_slices', sa.Column('jianying_status', sa.String(length=50), nullable=True, server_default='pending', comment='Jianying导出状态'))
    op.add_column('video_slices', sa.Column('jianying_task_id', sa.String(length=255), nullable=True, comment='Jianying导出的CeleryTaskID'))
    op.add_column('video_slices', sa.Column('jianying_draft_url', sa.Text(), nullable=True, comment='Jianying草稿文件URL'))
    op.add_column('video_slices', sa.Column('jianying_error_message', sa.Text(), nullable=True, comment='Jianying导出错误信息'))


def downgrade():
    # Remove Jianying fields from video_slices table
    op.drop_column('video_slices', 'jianying_error_message')
    op.drop_column('video_slices', 'jianying_draft_url')
    op.drop_column('video_slices', 'jianying_task_id')
    op.drop_column('video_slices', 'jianying_status')