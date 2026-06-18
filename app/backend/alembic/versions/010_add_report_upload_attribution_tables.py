"""Add report upload attribution tables.

Revision ID: 010_add_report_attribution
Revises: 009_add_asin_business_profiles
Create Date: 2026-06-17
"""

from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "010_add_report_attribution"
down_revision: Union[str, None] = "009_add_asin_business_profiles"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    if not _has_table(inspector, table_name):
        return False
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _add_column_if_missing(inspector, table_name: str, column: sa.Column) -> None:
    if _has_table(inspector, table_name) and not _has_column(inspector, table_name, column.name):
        op.add_column(table_name, column)


def _create_index_if_missing(inspector, table_name: str, index_name: str, columns: list[str]) -> None:
    if not _has_table(inspector, table_name):
        return
    indexes = {index["name"] for index in inspector.get_indexes(table_name)}
    if index_name not in indexes:
        op.create_index(index_name, table_name, columns, unique=False)


def upgrade() -> None:
    inspector = inspect(op.get_bind())

    for column in (
        sa.Column("page_views", sa.Integer(), nullable=True),
        sa.Column("units_ordered", sa.Integer(), nullable=True),
        sa.Column("impressions", sa.Integer(), nullable=True),
    ):
        _add_column_if_missing(inspector, "asin_daily_snapshots", column)

    for column in (
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column("uploaded_by", sa.String(), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=True),
    ):
        _add_column_if_missing(inspector, "report_uploads", column)

    _add_column_if_missing(inspector, "asin_execution_logs", sa.Column("source", sa.String(), nullable=True))

    if not _has_table(inspector, "asin_sku_maps"):
        op.create_table(
            "asin_sku_maps",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("seller_id", sa.String(), nullable=False),
            sa.Column("store_id", sa.String(), nullable=False),
            sa.Column("marketplace", sa.String(), nullable=False),
            sa.Column("asin", sa.String(), nullable=False),
            sa.Column("sku", sa.String(), nullable=True),
            sa.Column("seller_sku", sa.String(), nullable=True),
            sa.Column("product_name", sa.Text(), nullable=True),
            sa.Column("status", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("seller_id", "store_id", "marketplace", "sku", name="uq_asin_sku_map_scope"),
        )

    if not _has_table(inspector, "ad_entity_asin_maps"):
        op.create_table(
            "ad_entity_asin_maps",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("seller_id", sa.String(), nullable=False),
            sa.Column("store_id", sa.String(), nullable=False),
            sa.Column("marketplace", sa.String(), nullable=False),
            sa.Column("asin", sa.String(), nullable=False),
            sa.Column("sku", sa.String(), nullable=True),
            sa.Column("campaign_id", sa.String(), nullable=True),
            sa.Column("campaign_name", sa.Text(), nullable=True),
            sa.Column("ad_group_id", sa.String(), nullable=True),
            sa.Column("ad_group_name", sa.Text(), nullable=True),
            sa.Column("ad_id", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _has_table(inspector, "report_row_staging"):
        op.create_table(
            "report_row_staging",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("report_id", sa.String(), nullable=False),
            sa.Column("seller_id", sa.String(), nullable=False),
            sa.Column("store_id", sa.String(), nullable=False),
            sa.Column("marketplace", sa.String(), nullable=False),
            sa.Column("asin", sa.String(), nullable=True),
            sa.Column("date", sa.Date(), nullable=True),
            sa.Column("row_number", sa.Integer(), nullable=False),
            sa.Column("report_type", sa.String(), nullable=False),
            sa.Column("match_status", sa.String(), nullable=False),
            sa.Column("raw_data", sa.Text(), nullable=True),
            sa.Column("normalized_data", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _has_table(inspector, "ad_product_daily"):
        op.create_table(
            "ad_product_daily",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("seller_id", sa.String(), nullable=False),
            sa.Column("store_id", sa.String(), nullable=False),
            sa.Column("marketplace", sa.String(), nullable=False),
            sa.Column("asin", sa.String(), nullable=False),
            sa.Column("sku", sa.String(), nullable=True),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("campaign_name", sa.Text(), nullable=True),
            sa.Column("campaign_id", sa.String(), nullable=True),
            sa.Column("ad_group_name", sa.Text(), nullable=True),
            sa.Column("ad_group_id", sa.String(), nullable=True),
            sa.Column("impressions", sa.Integer(), nullable=True),
            sa.Column("clicks", sa.Integer(), nullable=True),
            sa.Column("spend", sa.Float(), nullable=True),
            sa.Column("sales", sa.Float(), nullable=True),
            sa.Column("orders", sa.Integer(), nullable=True),
            sa.Column("units", sa.Integer(), nullable=True),
            sa.Column("ctr", sa.Float(), nullable=True),
            sa.Column("cpc", sa.Float(), nullable=True),
            sa.Column("acos", sa.Float(), nullable=True),
            sa.Column("roas", sa.Float(), nullable=True),
            sa.Column("source_report_id", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _has_table(inspector, "ad_search_term_daily"):
        op.create_table(
            "ad_search_term_daily",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("seller_id", sa.String(), nullable=False),
            sa.Column("store_id", sa.String(), nullable=False),
            sa.Column("marketplace", sa.String(), nullable=False),
            sa.Column("asin", sa.String(), nullable=False),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("campaign_name", sa.Text(), nullable=True),
            sa.Column("ad_group_name", sa.Text(), nullable=True),
            sa.Column("keyword", sa.Text(), nullable=True),
            sa.Column("match_type", sa.String(), nullable=True),
            sa.Column("customer_search_term", sa.Text(), nullable=True),
            sa.Column("impressions", sa.Integer(), nullable=True),
            sa.Column("clicks", sa.Integer(), nullable=True),
            sa.Column("spend", sa.Float(), nullable=True),
            sa.Column("sales", sa.Float(), nullable=True),
            sa.Column("orders", sa.Integer(), nullable=True),
            sa.Column("units", sa.Integer(), nullable=True),
            sa.Column("ctr", sa.Float(), nullable=True),
            sa.Column("cpc", sa.Float(), nullable=True),
            sa.Column("acos", sa.Float(), nullable=True),
            sa.Column("roas", sa.Float(), nullable=True),
            sa.Column("source_report_id", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _has_table(inspector, "ad_target_daily"):
        op.create_table(
            "ad_target_daily",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("seller_id", sa.String(), nullable=False),
            sa.Column("store_id", sa.String(), nullable=False),
            sa.Column("marketplace", sa.String(), nullable=False),
            sa.Column("asin", sa.String(), nullable=False),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("campaign_name", sa.Text(), nullable=True),
            sa.Column("ad_group_name", sa.Text(), nullable=True),
            sa.Column("targeting", sa.Text(), nullable=True),
            sa.Column("targeting_type", sa.String(), nullable=True),
            sa.Column("match_type", sa.String(), nullable=True),
            sa.Column("impressions", sa.Integer(), nullable=True),
            sa.Column("clicks", sa.Integer(), nullable=True),
            sa.Column("spend", sa.Float(), nullable=True),
            sa.Column("sales", sa.Float(), nullable=True),
            sa.Column("orders", sa.Integer(), nullable=True),
            sa.Column("units", sa.Integer(), nullable=True),
            sa.Column("ctr", sa.Float(), nullable=True),
            sa.Column("cpc", sa.Float(), nullable=True),
            sa.Column("acos", sa.Float(), nullable=True),
            sa.Column("roas", sa.Float(), nullable=True),
            sa.Column("source_report_id", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = inspect(op.get_bind())
    for table_name, indexes in {
        "asin_sku_maps": [("ix_asin_sku_map_scope", ["seller_id", "store_id", "marketplace", "asin"])],
        "ad_entity_asin_maps": [
            ("ix_ad_entity_asin_map_scope", ["seller_id", "store_id", "marketplace", "asin"]),
            ("ix_ad_entity_asin_map_entity", ["campaign_id", "ad_group_id", "ad_id"]),
        ],
        "report_row_staging": [
            ("ix_report_row_staging_scope", ["seller_id", "store_id", "marketplace", "asin"]),
            ("ix_report_row_staging_report", ["report_id", "match_status"]),
        ],
        "ad_product_daily": [("ix_ad_product_daily_scope", ["seller_id", "store_id", "marketplace", "asin", "date"])],
        "ad_search_term_daily": [("ix_ad_search_term_daily_scope", ["seller_id", "store_id", "marketplace", "asin", "date"])],
        "ad_target_daily": [("ix_ad_target_daily_scope", ["seller_id", "store_id", "marketplace", "asin", "date"])],
    }.items():
        for index_name, columns in indexes:
            _create_index_if_missing(inspector, table_name, index_name, columns)


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    for table_name in (
        "ad_target_daily",
        "ad_search_term_daily",
        "ad_product_daily",
        "report_row_staging",
        "ad_entity_asin_maps",
        "asin_sku_maps",
    ):
        if _has_table(inspector, table_name):
            op.drop_table(table_name)
