"""add processing status tables

Revision ID: 001_add_processing_status_tables
Revises: 
Create Date: 2025-07-30 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # 检查列是否存在，如果不存在才添加
    bind = op.get_bind()
    inspector = sa.engine.reflection.Inspector.from_engine(bind)
    
    # 获取videos表的现有列
    existing_columns = [column['name'] for column in inspector.get_columns('videos')]
    
    # 添加视频表的新字段（如果不存在）
    columns_to_add = {
        'processing_stage': sa.Column('processing_stage', sa.String(50), nullable=True),
        'processing_progress': sa.Column('processing_progress', sa.Float, nullable=False, server_default='0.0'),
        'processing_message': sa.Column('processing_message', sa.String(500), nullable=True),
        'processing_error': sa.Column('processing_error', sa.Text, nullable=True),
        'processing_started_at': sa.Column('processing_started_at', sa.DateTime(timezone=True), nullable=True),
        'processing_completed_at': sa.Column('processing_completed_at', sa.DateTime(timezone=True), nullable=True),
        'processing_metadata': sa.Column('processing_metadata', sa.JSON(), nullable=True, server_default='{}')
    }
    
    for column_name, column_def in columns_to_add.items():
        if column_name not in existing_columns:
            op.add_column('videos', column_def)
            print(f"Added column: {column_name}")
        else:
            print(f"Column already exists: {column_name}")

    # 检查表是否存在，如果不存在才创建
    try:
        inspector.get_table_names()
        existing_tables = inspector.get_table_names()
    except:
        existing_tables = []
    
    if 'processing_tasks' not in existing_tables:
        # 创建处理任务表
        op.create_table('processing_tasks',
            sa.Column('id', sa.Integer, primary_key=True, index=True),
            sa.Column('video_id', sa.Integer, sa.ForeignKey('videos.id'), nullable=False),
            sa.Column('task_type', sa.String(50), nullable=False),
            sa.Column('task_name', sa.String(200), nullable=False),
            sa.Column('celery_task_id', sa.String(255), unique=True, index=True),
            sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
            sa.Column('progress', sa.Float, nullable=False, server_default='0.0'),
            sa.Column('stage', sa.String(50), nullable=True),
            sa.Column('message', sa.String(500), nullable=True),
            sa.Column('error_message', sa.Text, nullable=True),
            sa.Column('input_data', sa.JSON(), nullable=True),
            sa.Column('output_data', sa.JSON(), nullable=True),
            sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('duration_seconds', sa.Float, nullable=False, server_default='0.0'),
            sa.Column('retry_count', sa.Integer, nullable=False, server_default='0'),
            sa.Column('max_retries', sa.Integer, nullable=False, server_default='3'),
            sa.Column('task_metadata', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now())
        )
        print("Created table: processing_tasks")
    else:
        print("Table already exists: processing_tasks")

    # 创建处理任务日志表
    if 'processing_task_logs' not in existing_tables:
        op.create_table('processing_task_logs',
            sa.Column('id', sa.Integer, primary_key=True, index=True),
            sa.Column('task_id', sa.Integer, sa.ForeignKey('processing_tasks.id'), nullable=False),
            sa.Column('old_status', sa.String(50), nullable=True),
            sa.Column('new_status', sa.String(50), nullable=False),
            sa.Column('message', sa.String(500), nullable=True),
            sa.Column('details', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
        )
        print("Created table: processing_task_logs")
    else:
        print("Table already exists: processing_task_logs")

    # 创建处理状态汇总表
    if 'processing_status' not in existing_tables:
        op.create_table('processing_status',
            sa.Column('id', sa.Integer, primary_key=True, index=True),
            sa.Column('video_id', sa.Integer, sa.ForeignKey('videos.id'), nullable=False, unique=True),
            sa.Column('overall_status', sa.String(50), nullable=False, server_default='pending'),
            sa.Column('overall_progress', sa.Float, nullable=False, server_default='0.0'),
            sa.Column('current_stage', sa.String(50), nullable=True),
            sa.Column('download_status', sa.String(50), nullable=False, server_default='pending'),
            sa.Column('download_progress', sa.Float, nullable=False, server_default='0.0'),
            sa.Column('extract_audio_status', sa.String(50), nullable=False, server_default='pending'),
            sa.Column('extract_audio_progress', sa.Float, nullable=False, server_default='0.0'),
            sa.Column('split_audio_status', sa.String(50), nullable=False, server_default='pending'),
            sa.Column('split_audio_progress', sa.Float, nullable=False, server_default='0.0'),
            sa.Column('generate_srt_status', sa.String(50), nullable=False, server_default='pending'),
            sa.Column('generate_srt_progress', sa.Float, nullable=False, server_default='0.0'),
            sa.Column('error_count', sa.Integer, nullable=False, server_default='0'),
            sa.Column('last_error', sa.Text, nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
        )
        print("Created table: processing_status")
    else:
        print("Table already exists: processing_status")

    # 创建索引（检查是否已存在）
    try:
        indexes = inspector.get_indexes('videos')
        existing_index_names = [idx['name'] for idx in indexes]
    except:
        existing_index_names = []
    
    if 'idx_processing_tasks_video_id' not in existing_index_names:
        op.create_index('idx_processing_tasks_video_id', 'processing_tasks', ['video_id'])
        print("Created index: idx_processing_tasks_video_id")
    
    if 'idx_processing_tasks_status' not in existing_index_names:
        op.create_index('idx_processing_tasks_status', 'processing_tasks', ['status'])
        print("Created index: idx_processing_tasks_status")
    
    if 'idx_processing_tasks_celery_task_id' not in existing_index_names:
        op.create_index('idx_processing_tasks_celery_task_id', 'processing_tasks', ['celery_task_id'])
        print("Created index: idx_processing_tasks_celery_task_id")
    
    if 'idx_processing_task_logs_task_id' not in existing_index_names:
        op.create_index('idx_processing_task_logs_task_id', 'processing_task_logs', ['task_id'])
        print("Created index: idx_processing_task_logs_task_id")
    
    if 'idx_processing_status_video_id' not in existing_index_names:
        op.create_index('idx_processing_status_video_id', 'processing_status', ['video_id'])
        print("Created index: idx_processing_status_video_id")

def downgrade():
    # 删除索引
    op.drop_index('idx_processing_status_video_id', 'processing_status')
    op.drop_index('idx_processing_task_logs_task_id', 'processing_task_logs')
    op.drop_index('idx_processing_tasks_celery_task_id', 'processing_tasks')
    op.drop_index('idx_processing_tasks_status', 'processing_tasks')
    op.drop_index('idx_processing_tasks_video_id', 'processing_tasks')

    # 删除表
    op.drop_table('processing_status')
    op.drop_table('processing_task_logs')
    op.drop_table('processing_tasks')

    # 删除视频表的字段
    op.drop_column('videos', 'processing_metadata')
    op.drop_column('videos', 'processing_completed_at')
    op.drop_column('videos', 'processing_started_at')
    op.drop_column('videos', 'processing_error')
    op.drop_column('videos', 'processing_message')
    op.drop_column('videos', 'processing_progress')
    op.drop_column('videos', 'processing_stage')