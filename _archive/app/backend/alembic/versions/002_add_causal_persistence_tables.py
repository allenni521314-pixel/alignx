"""
添加因果系统持久化表 - 第二次迁移

Revision ID: 002_add_causal_persistence
Revises: 001_add_causal_diagnosis_fields
Create Date: 2026-05-14

新增内容：
1. review_causal_validations 表 - 评论因果验证结果
2. causal_ab_comparisons 表 - 因果A/B对比结果
3. batch_causal_tasks 表 - 批量任务持久化存储
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision: str = '002_add_causal_persistence'
down_revision: Union[str, None] = '001_add_causal_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级：创建3个新的持久化表"""

    # 1. 评论因果验证结果表
    op.create_table(
        'review_causal_validations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('asin', sa.String(length=10), nullable=True),
        sa.Column('marketplace', sa.String(length=2), default='US'),
        sa.Column('listing_title', sa.String(length=500), nullable=True),
        sa.Column('overall_honesty_score', sa.Float(), nullable=True, comment='整体因果诚信度得分 0-100'),
        sa.Column('total_claims_analyzed', sa.Integer(), default=0, comment='分析的宣称总数'),
        sa.Column('total_reviews_used', sa.Integer(), default=0, comment='使用的评论数量'),
        sa.Column('claims_validation', sa.JSON(), nullable=True),
        sa.Column('undisclosed_effects', sa.JSON(), nullable=True),
        sa.Column('optimization_suggestions', sa.JSON(), nullable=True),
        sa.Column('validation_summary', sa.JSON(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True, comment='验证置信度'),
        sa.Column('analysis_version', sa.String(length=20), default='1.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_review_causal_validations_user_id'), 'review_causal_validations', ['user_id'], unique=False)
    op.create_index(op.f('ix_review_causal_validations_asin'), 'review_causal_validations', ['asin'], unique=False)

    # 2. 因果A/B对比结果表
    op.create_table(
        'causal_ab_comparisons',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('variant_a_label', sa.String(length=100), default='A'),
        sa.Column('variant_b_label', sa.String(length=100), default='B'),
        sa.Column('variant_a_info', sa.JSON(), nullable=True),
        sa.Column('variant_b_info', sa.JSON(), nullable=True),
        sa.Column('winner', sa.String(length=10), comment='A / B / tie'),
        sa.Column('win_margin', sa.Float(), comment='获胜优势 0-100'),
        sa.Column('confidence_score', sa.Float(), comment='预测置信度 0-100'),
        sa.Column('dimension_comparison', sa.JSON(), nullable=True),
        sa.Column('key_strengths_a', sa.JSON(), nullable=True),
        sa.Column('key_strengths_b', sa.JSON(), nullable=True),
        sa.Column('key_weaknesses_a', sa.JSON(), nullable=True),
        sa.Column('key_weaknesses_b', sa.JSON(), nullable=True),
        sa.Column('predicted_conversion_impact', sa.JSON(), nullable=True),
        sa.Column('actionable_recommendations', sa.JSON(), nullable=True),
        sa.Column('text_report', sa.String(), nullable=True),
        sa.Column('full_diagnosis_a', sa.JSON(), nullable=True),
        sa.Column('analysis_version', sa.String(length=20), default='1.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_causal_ab_comparisons_user_id'), 'causal_ab_comparisons', ['user_id'], unique=False)

    # 3. 批量因果分析任务表
    op.create_table(
        'batch_causal_tasks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('batch_id', sa.String(length=50), unique=True, nullable=False, comment='批次ID'),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('task_type', sa.String(length=50), comment='任务类型: diagnosis / review_validation / ab_comparison'),
        sa.Column('marketplace', sa.String(length=2), default='US'),
        sa.Column('total_items', sa.Integer(), default=0, comment='总项目数'),
        sa.Column('completed_items', sa.Integer(), default=0, comment='已完成数'),
        sa.Column('failed_items', sa.Integer(), default=0, comment='失败数'),
        sa.Column('status', sa.String(length=20), default='pending', comment='pending / running / completed / failed / partial_success'),
        sa.Column('progress_percent', sa.Float(), default=0.0),
        sa.Column('input_items', sa.JSON(), nullable=True, comment='输入的ASIN列表'),
        sa.Column('results', sa.JSON(), nullable=True, comment='分析结果列表'),
        sa.Column('errors', sa.JSON(), nullable=True, comment='错误列表'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('analysis_version', sa.String(length=20), default='1.0'),
        sa.Column('execution_time_seconds', sa.Float(), comment='执行耗时（秒）'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_batch_causal_tasks_batch_id'), 'batch_causal_tasks', ['batch_id'], unique=True)
    op.create_index(op.f('ix_batch_causal_tasks_user_id'), 'batch_causal_tasks', ['user_id'], unique=False)


def downgrade() -> None:
    """回滚：删除3个新表"""
    op.drop_index(op.f('ix_batch_causal_tasks_user_id'), table_name='batch_causal_tasks')
    op.drop_index(op.f('ix_batch_causal_tasks_batch_id'), table_name='batch_causal_tasks')
    op.drop_table('batch_causal_tasks')

    op.drop_index(op.f('ix_causal_ab_comparisons_user_id'), table_name='causal_ab_comparisons')
    op.drop_table('causal_ab_comparisons')

    op.drop_index(op.f('ix_review_causal_validations_asin'), table_name='review_causal_validations')
    op.drop_index(op.f('ix_review_causal_validations_user_id'), table_name='review_causal_validations')
    op.drop_table('review_causal_validations')
