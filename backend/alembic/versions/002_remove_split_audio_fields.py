"""Remove split audio fields from processing_status table

Revision ID: 002_remove_split_audio_fields
Revises: 001_add_processing_status_tables
Create Date: 2024-01-XX

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002_remove_split_audio_fields'
down_revision = '001_add_processing_status_tables'
branch_labels = None
depends_on = None


def upgrade():
    """Remove split_audio fields from processing_status table"""
    
    # Check if columns exist before dropping them
    bind = op.get_bind()
    inspector = sa.engine.reflection.Inspector.from_engine(bind)
    columns = [column['name'] for column in inspector.get_columns('processing_status')]
    
    # Drop the columns if they exist
    with op.batch_alter_table('processing_status', schema=None) as batch_op:
        if 'split_audio_progress' in columns:
            batch_op.drop_column('split_audio_progress')
        if 'split_audio_status' in columns:
            batch_op.drop_column('split_audio_status')


def downgrade():
    """Add back split_audio fields to processing_status table"""
    
    # Add back the columns for rollback
    with op.batch_alter_table('processing_status', schema=None) as batch_op:
        batch_op.add_column(sa.String(length=50), nullable=True, server_default='pending', name='split_audio_status')
        batch_op.add_column(sa.Float(), nullable=True, server_default='0.0', name='split_audio_progress')