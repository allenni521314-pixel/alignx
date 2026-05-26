"""Add user ownership to optimization timeline.

Revision ID: 005_add_timeline_user_id
Revises: 004_add_hypothesis_ad_data
Create Date: 2026-05-26
"""

from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "005_add_timeline_user_id"
down_revision: Union[str, None] = "004_add_hypothesis_ad_data"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    if "optimization_timeline" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("optimization_timeline")}
    if "user_id" not in columns:
        op.add_column("optimization_timeline", sa.Column("user_id", sa.String(), nullable=True))

    indexes = {index["name"] for index in inspector.get_indexes("optimization_timeline")}
    if "ix_optimization_timeline_user_id" not in indexes:
        op.create_index(op.f("ix_optimization_timeline_user_id"), "optimization_timeline", ["user_id"], unique=False)


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    if "optimization_timeline" not in inspector.get_table_names():
        return

    indexes = {index["name"] for index in inspector.get_indexes("optimization_timeline")}
    if "ix_optimization_timeline_user_id" in indexes:
        op.drop_index(op.f("ix_optimization_timeline_user_id"), table_name="optimization_timeline")

    columns = {column["name"] for column in inspector.get_columns("optimization_timeline")}
    if "user_id" in columns:
        op.drop_column("optimization_timeline", "user_id")
