"""add_cascade_delete_relationship_between_LLMAnalysis_and_VideoSlice

Revision ID: 61d5bd275ad2
Revises: 6a2620b80854
Create Date: 2025-08-17 00:06:16.843969

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '61d5bd275ad2'
down_revision: Union[str, Sequence[str], None] = '6a2620b80854'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add cascade delete constraint."""
    # 删除现有的外键约束
    op.drop_constraint('video_slices_ibfk_2', 'video_slices', type_='foreignkey')
    
    # 添加带级联删除的新外键约束
    op.create_foreign_key(
        'video_slices_llm_analysis_id_fkey',
        'video_slices',
        'llm_analyses',
        ['llm_analysis_id'],
        ['id'],
        ondelete='CASCADE'
    )


def downgrade() -> None:
    """Downgrade schema - remove cascade delete constraint."""
    # 删除带级联删除的外键约束
    op.drop_constraint('video_slices_llm_analysis_id_fkey', 'video_slices', type_='foreignkey')
    
    # 恢复原来的外键约束（不带级联删除）
    op.create_foreign_key(
        'video_slices_ibfk_2',
        'video_slices',
        'llm_analyses',
        ['llm_analysis_id'],
        ['id']
    )
