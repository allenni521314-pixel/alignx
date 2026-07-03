"""
添加因果诊断字段和人类状态体表

Revision ID: 001_add_causal_fields
Revises: ecd08c6af770
Create Date: 2026-05-14 12:00:00.000000

升级内容：
1. 在 listing_diagnoses 表中添加 3 个因果维度分数字段
2. 在 listing_diagnoses 表中添加 causal_diagnosis_report 字段
3. 创建全新的 human_state_body 表（人类状态体核心表）
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_add_causal_fields'
down_revision: Union[str, Sequence[str], None] = '6750bf3f308d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: 添加因果诊断相关字段"""
    
    # ========================================
    # 1. 在 listing_diagnoses 表中添加因果维度字段
    # ========================================
    op.add_column(
        'listing_diagnoses',
        sa.Column('score_causal_state_gap_coverage', sa.Float(), nullable=True,
                  comment='因果维度1：状态差距覆盖度 - 商品解决了哪些人类状态差距')
    )
    op.add_column(
        'listing_diagnoses',
        sa.Column('score_causal_mechanism_clarity', sa.Float(), nullable=True,
                  comment='因果维度2：因果机制清晰度 - 商品解决问题的作用机制是否清晰可信')
    )
    op.add_column(
        'listing_diagnoses',
        sa.Column('score_causal_side_effect_transparency', sa.Float(), nullable=True,
                  comment='因果维度3：副作用透明度 - 是否诚实告知产品可能带来的负面代价')
    )
    op.add_column(
        'listing_diagnoses',
        sa.Column('causal_diagnosis_report', sa.Text(), nullable=True,
                  comment='完整的因果诊断报告JSON')
    )
    
    # ========================================
    # 2. 创建人类状态体核心表
    # ========================================
    op.create_table(
        'human_state_body',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.String(), nullable=True, comment='关联用户ID'),
        sa.Column('asin', sa.String(length=10), nullable=True, comment='产品ASIN'),
        sa.Column('marketplace', sa.String(length=2), default='US', comment='站点'),
        sa.Column('listing_diagnosis_id', sa.Integer(), nullable=True, comment='关联的Listing诊断ID'),
        sa.Column('product_id', sa.Integer(), nullable=True, comment='产品ID'),
        
        # 核心状态差距数据
        sa.Column('state_gaps', sa.JSON(), nullable=True, comment='识别到的状态差距列表'),
        sa.Column('causal_mechanisms', sa.JSON(), nullable=True, comment='因果机制分析结果'),
        sa.Column('side_effects', sa.JSON(), nullable=True, comment='副作用检测结果'),
        sa.Column('population_heterogeneity', sa.JSON(), nullable=True, comment='人群异质性分析'),
        
        # 因果三维度得分
        sa.Column('overall_causal_score', sa.Float(), nullable=True, comment='整体因果质量得分'),
        sa.Column('state_gap_coverage_score', sa.Float(), nullable=True, comment='状态差距覆盖度得分'),
        sa.Column('mechanism_clarity_score', sa.Float(), nullable=True, comment='因果机制清晰度得分'),
        sa.Column('side_effect_transparency_score', sa.Float(), nullable=True, comment='副作用透明度得分'),
        
        # 元数据
        sa.Column('source_type', sa.String(length=50), nullable=True, comment='数据来源类型'),
        sa.Column('confidence_level', sa.Float(), nullable=True, comment='分析置信度'),
        sa.Column('analysis_version', sa.String(length=20), default='1.0', comment='分析版本'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_human_state_body_id'), 'human_state_body', ['id'], unique=False)
    op.create_index(op.f('ix_human_state_body_asin'), 'human_state_body', ['asin'], unique=False)


def downgrade() -> None:
    """Downgrade schema: 回滚迁移"""
    
    # 1. 删除人类状态体表
    op.drop_index(op.f('ix_human_state_body_asin'), table_name='human_state_body')
    op.drop_index(op.f('ix_human_state_body_id'), table_name='human_state_body')
    op.drop_table('human_state_body')
    
    # 2. 删除 listing_diagnoses 表中的因果字段
    op.drop_column('listing_diagnoses', 'causal_diagnosis_report')
    op.drop_column('listing_diagnoses', 'score_causal_side_effect_transparency')
    op.drop_column('listing_diagnoses', 'score_causal_mechanism_clarity')
    op.drop_column('listing_diagnoses', 'score_causal_state_gap_coverage')
