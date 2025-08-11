"""Add CapCut fields to video_slice table

Revision ID: 004_add_capcut_fields_to_video_slice
Revises: 003
Create Date: 2025-01-11 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade():
    # Add CapCut fields to video_slices table
    op.add_column('video_slices', sa.Column('capcut_status', sa.String(length=50), nullable=True, server_default='pending'))
    op.add_column('video_slices', sa.Column('capcut_task_id', sa.String(length=255), nullable=True))
    op.add_column('video_slices', sa.Column('capcut_draft_url', sa.Text(), nullable=True))
    op.add_column('video_slices', sa.Column('capcut_error_message', sa.Text(), nullable=True))


def downgrade():
    # Remove CapCut fields from video_slices table
    op.drop_column('video_slices', 'capcut_error_message')
    op.drop_column('video_slices', 'capcut_draft_url')
    op.drop_column('video_slices', 'capcut_task_id')
    op.drop_column('video_slices', 'capcut_status')