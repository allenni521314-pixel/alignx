"""Add ASIN business profile tables.

Revision ID: 009_add_asin_business_profiles
Revises: 008_add_opc_os_executions
Create Date: 2026-06-17
"""

from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "009_add_asin_business_profiles"
down_revision: Union[str, None] = "008_add_opc_os_executions"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _create_index_if_missing(inspector, table_name: str, index_name: str, columns: list[str]) -> None:
    indexes = {index["name"] for index in inspector.get_indexes(table_name)}
    if index_name not in indexes:
        op.create_index(index_name, table_name, columns, unique=False)


def upgrade() -> None:
    inspector = inspect(op.get_bind())

    if not _has_table(inspector, "asin_profiles"):
        op.create_table(
            "asin_profiles",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("seller_id", sa.String(), nullable=False),
            sa.Column("store_id", sa.String(), nullable=False),
            sa.Column("marketplace", sa.String(), nullable=False),
            sa.Column("asin", sa.String(), nullable=False),
            sa.Column("sku", sa.String(), nullable=True),
            sa.Column("brand", sa.String(), nullable=True),
            sa.Column("product_name", sa.Text(), nullable=True),
            sa.Column("category", sa.Text(), nullable=True),
            sa.Column("launch_date", sa.Date(), nullable=True),
            sa.Column("current_price", sa.Float(), nullable=True),
            sa.Column("lifecycle_stage", sa.String(), nullable=True),
            sa.Column("overall_score", sa.Float(), nullable=True),
            sa.Column("traffic_score", sa.Float(), nullable=True),
            sa.Column("ctr_score", sa.Float(), nullable=True),
            sa.Column("cvr_score", sa.Float(), nullable=True),
            sa.Column("ads_score", sa.Float(), nullable=True),
            sa.Column("profit_score", sa.Float(), nullable=True),
            sa.Column("competition_score", sa.Float(), nullable=True),
            sa.Column("title_score", sa.Float(), nullable=True),
            sa.Column("main_image_score", sa.Float(), nullable=True),
            sa.Column("gallery_score", sa.Float(), nullable=True),
            sa.Column("aplus_score", sa.Float(), nullable=True),
            sa.Column("bullet_score", sa.Float(), nullable=True),
            sa.Column("review_score", sa.Float(), nullable=True),
            sa.Column("price_score", sa.Float(), nullable=True),
            sa.Column("sessions", sa.Integer(), nullable=True),
            sa.Column("ctr", sa.Float(), nullable=True),
            sa.Column("cvr", sa.Float(), nullable=True),
            sa.Column("organic_sales_ratio", sa.Float(), nullable=True),
            sa.Column("ads_sales_ratio", sa.Float(), nullable=True),
            sa.Column("acos", sa.Float(), nullable=True),
            sa.Column("tacos", sa.Float(), nullable=True),
            sa.Column("keyword_count", sa.Integer(), nullable=True),
            sa.Column("current_primary_problem", sa.Text(), nullable=True),
            sa.Column("priority_actions", sa.Text(), nullable=True),
            sa.Column("confidence_score", sa.Float(), nullable=True),
            sa.Column("traffic_dependency", sa.Float(), nullable=True),
            sa.Column("listing_dependency", sa.Float(), nullable=True),
            sa.Column("advertising_dependency", sa.Float(), nullable=True),
            sa.Column("price_sensitivity", sa.Float(), nullable=True),
            sa.Column("validation_success_rate", sa.Float(), nullable=True),
            sa.Column("next_recommended_action", sa.Text(), nullable=True),
            sa.Column("market_demand", sa.Text(), nullable=True),
            sa.Column("keyword_opportunities", sa.Text(), nullable=True),
            sa.Column("market_capacity", sa.Text(), nullable=True),
            sa.Column("competitor_benchmarks", sa.Text(), nullable=True),
            sa.Column("traffic_strategy", sa.Text(), nullable=True),
            sa.Column("keyword_strategy", sa.Text(), nullable=True),
            sa.Column("ad_strategy", sa.Text(), nullable=True),
            sa.Column("data_source", sa.String(), nullable=True),
            sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("seller_id", "store_id", "marketplace", "asin", name="uq_asin_profile_scope"),
        )

    if not _has_table(inspector, "asin_daily_snapshots"):
        op.create_table(
            "asin_daily_snapshots",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("seller_id", sa.String(), nullable=False),
            sa.Column("store_id", sa.String(), nullable=False),
            sa.Column("marketplace", sa.String(), nullable=False),
            sa.Column("asin", sa.String(), nullable=False),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("sessions", sa.Integer(), nullable=True),
            sa.Column("clicks", sa.Integer(), nullable=True),
            sa.Column("orders", sa.Integer(), nullable=True),
            sa.Column("sales", sa.Float(), nullable=True),
            sa.Column("ctr", sa.Float(), nullable=True),
            sa.Column("cvr", sa.Float(), nullable=True),
            sa.Column("acos", sa.Float(), nullable=True),
            sa.Column("tacos", sa.Float(), nullable=True),
            sa.Column("ad_spend", sa.Float(), nullable=True),
            sa.Column("ad_sales", sa.Float(), nullable=True),
            sa.Column("organic_sales", sa.Float(), nullable=True),
            sa.Column("total_sales", sa.Float(), nullable=True),
            sa.Column("inventory", sa.Integer(), nullable=True),
            sa.Column("buybox_status", sa.String(), nullable=True),
            sa.Column("source_report_id", sa.String(), nullable=True),
            sa.Column("data_source", sa.String(), nullable=True),
            sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("seller_id", "store_id", "marketplace", "asin", "date", name="uq_asin_daily_snapshot_scope"),
        )

    if not _has_table(inspector, "report_uploads"):
        op.create_table(
            "report_uploads",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("report_id", sa.String(), nullable=False),
            sa.Column("seller_id", sa.String(), nullable=False),
            sa.Column("store_id", sa.String(), nullable=False),
            sa.Column("marketplace", sa.String(), nullable=True),
            sa.Column("report_type", sa.String(), nullable=False),
            sa.Column("original_filename", sa.String(), nullable=True),
            sa.Column("upload_time", sa.DateTime(timezone=True), nullable=True),
            sa.Column("parse_status", sa.String(), nullable=False, server_default="Pending"),
            sa.Column("parse_error", sa.Text(), nullable=True),
            sa.Column("date_range_start", sa.Date(), nullable=True),
            sa.Column("date_range_end", sa.Date(), nullable=True),
            sa.Column("source_file_url", sa.Text(), nullable=True),
            sa.Column("data_source", sa.String(), nullable=True),
            sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("report_id"),
        )

    if not _has_table(inspector, "validation_tasks"):
        op.create_table(
            "validation_tasks",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("validation_id", sa.String(), nullable=False),
            sa.Column("seller_id", sa.String(), nullable=False),
            sa.Column("store_id", sa.String(), nullable=False),
            sa.Column("marketplace", sa.String(), nullable=False),
            sa.Column("asin", sa.String(), nullable=False),
            sa.Column("validation_type", sa.String(), nullable=False),
            sa.Column("problem", sa.Text(), nullable=True),
            sa.Column("hypothesis", sa.Text(), nullable=True),
            sa.Column("action_plan", sa.Text(), nullable=True),
            sa.Column("target_metric", sa.String(), nullable=True),
            sa.Column("baseline_start_date", sa.Date(), nullable=True),
            sa.Column("baseline_end_date", sa.Date(), nullable=True),
            sa.Column("test_start_date", sa.Date(), nullable=True),
            sa.Column("test_end_date", sa.Date(), nullable=True),
            sa.Column("result_start_date", sa.Date(), nullable=True),
            sa.Column("result_end_date", sa.Date(), nullable=True),
            sa.Column("baseline_value", sa.Float(), nullable=True),
            sa.Column("target_value", sa.Float(), nullable=True),
            sa.Column("result_value", sa.Float(), nullable=True),
            sa.Column("improvement_rate", sa.Float(), nullable=True),
            sa.Column("confidence_score", sa.Float(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="Pending"),
            sa.Column("data_source", sa.String(), nullable=True),
            sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("validation_id"),
        )

    if not _has_table(inspector, "asin_execution_logs"):
        op.create_table(
            "asin_execution_logs",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("execution_id", sa.String(), nullable=False),
            sa.Column("validation_id", sa.String(), nullable=False),
            sa.Column("seller_id", sa.String(), nullable=False),
            sa.Column("store_id", sa.String(), nullable=False),
            sa.Column("marketplace", sa.String(), nullable=False),
            sa.Column("asin", sa.String(), nullable=False),
            sa.Column("action_type", sa.String(), nullable=False),
            sa.Column("before_value", sa.Text(), nullable=True),
            sa.Column("after_value", sa.Text(), nullable=True),
            sa.Column("executed_by", sa.String(), nullable=True),
            sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("data_source", sa.String(), nullable=True),
            sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["validation_id"], ["validation_tasks.validation_id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("execution_id"),
        )

    if not _has_table(inspector, "ai_decision_traces"):
        op.create_table(
            "ai_decision_traces",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("decision_id", sa.String(), nullable=False),
            sa.Column("seller_id", sa.String(), nullable=False),
            sa.Column("store_id", sa.String(), nullable=False),
            sa.Column("marketplace", sa.String(), nullable=False),
            sa.Column("asin", sa.String(), nullable=False),
            sa.Column("related_validation_id", sa.String(), nullable=True),
            sa.Column("decision_type", sa.String(), nullable=False),
            sa.Column("conclusion", sa.Text(), nullable=True),
            sa.Column("evidence_metrics", sa.Text(), nullable=True),
            sa.Column("reasoning_summary", sa.Text(), nullable=True),
            sa.Column("confidence_score", sa.Float(), nullable=True),
            sa.Column("recommended_action", sa.Text(), nullable=True),
            sa.Column("data_source", sa.String(), nullable=True),
            sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("decision_id"),
        )

    if not _has_table(inspector, "metric_dictionary"):
        op.create_table(
            "metric_dictionary",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("metric_key", sa.String(), nullable=False),
            sa.Column("metric_name", sa.String(), nullable=False),
            sa.Column("formula", sa.Text(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("metric_key", name="uq_metric_dictionary_key"),
        )

    if not _has_table(inspector, "listing_versions"):
        op.create_table(
            "listing_versions",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("seller_id", sa.String(), nullable=False),
            sa.Column("store_id", sa.String(), nullable=False),
            sa.Column("marketplace", sa.String(), nullable=False),
            sa.Column("asin", sa.String(), nullable=False),
            sa.Column("version", sa.String(), nullable=False),
            sa.Column("modified_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("change_content", sa.Text(), nullable=True),
            sa.Column("change_reason", sa.Text(), nullable=True),
            sa.Column("data_source", sa.String(), nullable=True),
            sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("seller_id", "store_id", "marketplace", "asin", "version", name="uq_listing_version_scope"),
        )

    if not _has_table(inspector, "asin_keyword_profiles"):
        op.create_table(
            "asin_keyword_profiles",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("seller_id", sa.String(), nullable=False),
            sa.Column("store_id", sa.String(), nullable=False),
            sa.Column("marketplace", sa.String(), nullable=False),
            sa.Column("asin", sa.String(), nullable=False),
            sa.Column("keyword", sa.String(), nullable=False),
            sa.Column("rank", sa.Integer(), nullable=True),
            sa.Column("traffic_share", sa.Float(), nullable=True),
            sa.Column("trend", sa.String(), nullable=True),
            sa.Column("data_source", sa.String(), nullable=True),
            sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("seller_id", "store_id", "marketplace", "asin", "keyword", name="uq_asin_keyword_scope"),
        )

    inspector = inspect(op.get_bind())
    for table_name, indexes in {
        "asin_profiles": [("ix_asin_profile_scope", ["seller_id", "store_id", "marketplace", "asin"])],
        "asin_daily_snapshots": [("ix_asin_daily_snapshot_scope", ["seller_id", "store_id", "marketplace", "asin", "date"])],
        "report_uploads": [("ix_report_upload_scope", ["seller_id", "store_id", "report_type"])],
        "validation_tasks": [("ix_validation_task_scope", ["seller_id", "store_id", "marketplace", "asin"])],
        "asin_execution_logs": [("ix_asin_execution_log_scope", ["validation_id", "asin"])],
        "ai_decision_traces": [("ix_ai_decision_trace_scope", ["seller_id", "store_id", "marketplace", "asin"])],
        "listing_versions": [("ix_listing_version_scope", ["seller_id", "store_id", "marketplace", "asin"])],
        "asin_keyword_profiles": [("ix_asin_keyword_profile_scope", ["seller_id", "store_id", "marketplace", "asin"])],
    }.items():
        if _has_table(inspector, table_name):
            for index_name, columns in indexes:
                _create_index_if_missing(inspector, table_name, index_name, columns)


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    for table_name in (
        "asin_keyword_profiles",
        "listing_versions",
        "metric_dictionary",
        "ai_decision_traces",
        "asin_execution_logs",
        "validation_tasks",
        "report_uploads",
        "asin_daily_snapshots",
        "asin_profiles",
    ):
        if _has_table(inspector, table_name):
            op.drop_table(table_name)
