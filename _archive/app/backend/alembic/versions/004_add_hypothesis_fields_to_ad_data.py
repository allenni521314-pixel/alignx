"""add hypothesis fields to ad_data

Revision ID: 004_add_hypothesis_ad_data
Revises: 003_add_price_tier
Create Date: 2026-05-25

"""
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "004_add_hypothesis_ad_data"
down_revision: Union[str, None] = "003_add_price_tier"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("ad_data", sa.Column("hypothesis_id", sa.String(), nullable=True))
    op.add_column("ad_data", sa.Column("keyword_group_id", sa.String(), nullable=True))
    op.add_column("ad_data", sa.Column("optimization_round", sa.Integer(), nullable=True, server_default="1"))
    op.create_index(op.f("ix_ad_data_hypothesis_id"), "ad_data", ["hypothesis_id"], unique=False)
    op.create_index(op.f("ix_ad_data_keyword_group_id"), "ad_data", ["keyword_group_id"], unique=False)
    op.create_index(op.f("ix_ad_data_optimization_round"), "ad_data", ["optimization_round"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ad_data_optimization_round"), table_name="ad_data")
    op.drop_index(op.f("ix_ad_data_keyword_group_id"), table_name="ad_data")
    op.drop_index(op.f("ix_ad_data_hypothesis_id"), table_name="ad_data")
    op.drop_column("ad_data", "optimization_round")
    op.drop_column("ad_data", "keyword_group_id")
    op.drop_column("ad_data", "hypothesis_id")
