"""Fix file_size column overflow issue by changing from Integer to BIGINT

Revision ID: 005_fix_file_size_column_overflow
Revises: 004_add_capcut_fields_to_video_slice
Create Date: 2025-08-16 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    # Alter the file_size column in videos table from Integer to BIGINT
    with op.batch_alter_table('videos', schema=None) as batch_op:
        batch_op.alter_column('file_size',
                              existing_type=sa.Integer(),
                              type_=sa.BigInteger(),
                              existing_nullable=True)


def downgrade():
    # Revert the file_size column in videos table from BIGINT to Integer
    with op.batch_alter_table('videos', schema=None) as batch_op:
        batch_op.alter_column('file_size',
                              existing_type=sa.BigInteger(),
                              type_=sa.Integer(),
                              existing_nullable=True)