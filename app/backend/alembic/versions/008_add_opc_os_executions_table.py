"""Add OPC OS execution records table.

Revision ID: 008_add_opc_os_executions
Revises: 007_add_core_engine
Create Date: 2026-06-03
"""

from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "008_add_opc_os_executions"
down_revision: Union[str, None] = "007_add_core_engine"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def _create_index_if_missing(inspector, table_name: str, index_name: str, columns: list[str]) -> None:
    indexes = {index["name"] for index in inspector.get_indexes(table_name)}
    if index_name not in indexes:
        op.create_index(index_name, table_name, columns, unique=False)


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    if "opc_os_executions" not in inspector.get_table_names():
        op.create_table(
            "opc_os_executions",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("object_type", sa.String(), nullable=False),
            sa.Column("object_id", sa.String(), nullable=False),
            sa.Column("opportunity_id", sa.String(), nullable=True),
            sa.Column("source_module", sa.String(), nullable=True),
            sa.Column("source_record_id", sa.Integer(), nullable=True),
            sa.Column("asin", sa.String(), nullable=True),
            sa.Column("title", sa.String(), nullable=True),
            sa.Column("status", sa.String(), nullable=True),
            sa.Column("payload", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
        )
    inspector = inspect(op.get_bind())
    for index_name, columns in (
        ("ix_opc_os_executions_id", ["id"]),
        ("ix_opc_os_executions_user_id", ["user_id"]),
        ("ix_opc_os_executions_object_type", ["object_type"]),
        ("ix_opc_os_executions_object_id", ["object_id"]),
        ("ix_opc_os_executions_opportunity_id", ["opportunity_id"]),
        ("ix_opc_os_executions_source_module", ["source_module"]),
        ("ix_opc_os_executions_source_record_id", ["source_record_id"]),
        ("ix_opc_os_executions_asin", ["asin"]),
        ("ix_opc_os_executions_status", ["status"]),
    ):
        _create_index_if_missing(inspector, "opc_os_executions", index_name, columns)


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    if "opc_os_executions" in inspector.get_table_names():
        op.drop_table("opc_os_executions")
