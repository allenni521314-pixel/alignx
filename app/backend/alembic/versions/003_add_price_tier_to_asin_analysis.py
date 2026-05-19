"""
新增ASIN选品第6维：价格带维度

Revision ID: 003_add_price_tier
Revises: 002_add_causal_persistence
Create Date: 2026-05-14

新增内容：
- score_5d_price_tier: 价格带维度评分 0-100
- price_tier_category: 价格带分类 (high/medium/low)
- price_tier_analysis: 详细价格带分析JSON
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision: str = '003_add_price_tier'
down_revision: Union[str, None] = '002_add_causal_persistence'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级：新增价格带维度字段"""
    op.add_column(
        'asin_analyses',
        sa.Column('score_5d_price_tier', sa.Float(), nullable=True, comment='第6维：价格带维度评分 0-100')
    )
    op.add_column(
        'asin_analyses',
        sa.Column('price_tier_category', sa.String(), nullable=True, comment='价格带分类: high/medium/low')
    )
    op.add_column(
        'asin_analyses',
        sa.Column('price_tier_analysis', sa.String(), nullable=True, comment='详细价格带分析JSON')
    )
    # 注意：score_5d_detail 的注释已经在模型中更新，不需要迁移（因为是字段注释，不是新增字段）


def downgrade() -> None:
    """回滚：删除价格带维度字段"""
    op.drop_column('asin_analyses', 'price_tier_analysis')
    op.drop_column('asin_analyses', 'price_tier_category')
    op.drop_column('asin_analyses', 'score_5d_price_tier')
