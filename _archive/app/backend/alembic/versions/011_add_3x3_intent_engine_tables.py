"""Add ASIN 3x3 intent engine tables.

Revision ID: 011_add_3x3_intent_engine
Revises: 010_add_report_attribution
Create Date: 2026-06-18
"""

from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "011_add_3x3_intent_engine"
down_revision: Union[str, None] = "010_add_report_attribution"
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
        sa.Column("matched_rows", sa.Integer(), nullable=True),
        sa.Column("unresolved_rows", sa.Integer(), nullable=True),
        sa.Column("ambiguous_rows", sa.Integer(), nullable=True),
        sa.Column("writable_rows", sa.Integer(), nullable=True),
        sa.Column("match_summary", sa.Text(), nullable=True),
    ):
        _add_column_if_missing(inspector, "report_uploads", column)

    for column in (
        sa.Column("match_method", sa.String(), nullable=True),
        sa.Column("extracted_asin", sa.String(), nullable=True),
        sa.Column("extracted_sku", sa.String(), nullable=True),
        sa.Column("campaign_id", sa.String(), nullable=True),
        sa.Column("ad_group_id", sa.String(), nullable=True),
        sa.Column("ad_id", sa.String(), nullable=True),
        sa.Column("matched_asin", sa.String(), nullable=True),
        sa.Column("candidate_matches", sa.Text(), nullable=True),
        sa.Column("is_writable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("resolution_status", sa.String(), nullable=True),
    ):
        _add_column_if_missing(inspector, "report_row_staging", column)

    for table_name in ("ad_search_term_daily", "ad_target_daily"):
        _add_column_if_missing(inspector, table_name, sa.Column("period_start", sa.Date(), nullable=True))
        _add_column_if_missing(inspector, table_name, sa.Column("period_end", sa.Date(), nullable=True))

    _add_column_if_missing(inspector, "validation_tasks", sa.Column("intent_decision_id", sa.String(), nullable=True))
    _add_column_if_missing(inspector, "asin_execution_logs", sa.Column("intent_decision_id", sa.String(), nullable=True))

    for column in (
        sa.Column("input_data_refs", sa.Text(), nullable=True),
        sa.Column("metric_snapshot", sa.Text(), nullable=True),
        sa.Column("semantic_evidence", sa.Text(), nullable=True),
        sa.Column("prompt_version", sa.String(), nullable=True),
        sa.Column("model_name", sa.String(), nullable=True),
    ):
        _add_column_if_missing(inspector, "ai_decision_traces", column)

    if not _has_table(inspector, "asin_listing_snapshots"):
        op.create_table(
            "asin_listing_snapshots",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("seller_id", sa.String(), nullable=False),
            sa.Column("store_id", sa.String(), nullable=False),
            sa.Column("marketplace", sa.String(), nullable=False),
            sa.Column("asin", sa.String(), nullable=False),
            sa.Column("title", sa.Text(), nullable=True),
            sa.Column("bullet_points", sa.Text(), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("aplus", sa.Text(), nullable=True),
            sa.Column("main_image", sa.Text(), nullable=True),
            sa.Column("secondary_images", sa.Text(), nullable=True),
            sa.Column("backend_terms", sa.Text(), nullable=True),
            sa.Column("price", sa.Float(), nullable=True),
            sa.Column("coupon", sa.Text(), nullable=True),
            sa.Column("snapshot_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("data_source", sa.String(), nullable=True),
            sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _has_table(inspector, "asin_intent_decisions"):
        op.create_table(
            "asin_intent_decisions",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("intent_decision_id", sa.String(), nullable=False),
            sa.Column("seller_id", sa.String(), nullable=False),
            sa.Column("store_id", sa.String(), nullable=False),
            sa.Column("marketplace", sa.String(), nullable=False),
            sa.Column("asin", sa.String(), nullable=False),
            sa.Column("intent_name", sa.String(), nullable=False),
            sa.Column("intent_description", sa.Text(), nullable=True),
            sa.Column("position_reception_result", sa.Text(), nullable=True),
            sa.Column("semantic_audit_result", sa.Text(), nullable=True),
            sa.Column("buyer_language_result", sa.Text(), nullable=True),
            sa.Column("intent_evidence_status", sa.String(), nullable=True),
            sa.Column("product_platform_safety_status", sa.String(), nullable=True),
            sa.Column("investment_value_status", sa.String(), nullable=True),
            sa.Column("reception_gap", sa.Text(), nullable=True),
            sa.Column("safe_expression", sa.Text(), nullable=True),
            sa.Column("blocked_expression", sa.Text(), nullable=True),
            sa.Column("recommended_action", sa.String(), nullable=False),
            sa.Column("priority_score", sa.Float(), nullable=True),
            sa.Column("confidence_score", sa.Float(), nullable=True),
            sa.Column("validation_task_id", sa.String(), nullable=True),
            sa.Column("validation_result", sa.String(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="Candidate"),
            sa.Column("data_source", sa.String(), nullable=True),
            sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("intent_decision_id"),
        )

    if not _has_table(inspector, "asin_intent_evidence"):
        op.create_table(
            "asin_intent_evidence",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("evidence_id", sa.String(), nullable=False),
            sa.Column("intent_decision_id", sa.String(), nullable=False),
            sa.Column("seller_id", sa.String(), nullable=False),
            sa.Column("store_id", sa.String(), nullable=False),
            sa.Column("marketplace", sa.String(), nullable=False),
            sa.Column("asin", sa.String(), nullable=False),
            sa.Column("intent_name", sa.String(), nullable=False),
            sa.Column("source_type", sa.String(), nullable=False),
            sa.Column("evidence_text", sa.Text(), nullable=True),
            sa.Column("metric_snapshot", sa.Text(), nullable=True),
            sa.Column("strength_score", sa.Float(), nullable=True),
            sa.Column("data_source", sa.String(), nullable=True),
            sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("evidence_id"),
        )

    if not _has_table(inspector, "asin_safe_expressions"):
        op.create_table(
            "asin_safe_expressions",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("safe_expression_id", sa.String(), nullable=False),
            sa.Column("intent_decision_id", sa.String(), nullable=True),
            sa.Column("seller_id", sa.String(), nullable=False),
            sa.Column("store_id", sa.String(), nullable=False),
            sa.Column("marketplace", sa.String(), nullable=False),
            sa.Column("asin", sa.String(), nullable=False),
            sa.Column("buyer_language", sa.Text(), nullable=True),
            sa.Column("seller_language", sa.Text(), nullable=True),
            sa.Column("safe_expression", sa.Text(), nullable=True),
            sa.Column("blocked_expression", sa.Text(), nullable=True),
            sa.Column("risk_reason", sa.Text(), nullable=True),
            sa.Column("evidence_required", sa.Text(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="Needs Evidence"),
            sa.Column("data_source", sa.String(), nullable=True),
            sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("safe_expression_id"),
        )

    if not _has_table(inspector, "asin_ai_memory"):
        op.create_table(
            "asin_ai_memory",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("seller_id", sa.String(), nullable=False),
            sa.Column("store_id", sa.String(), nullable=False),
            sa.Column("marketplace", sa.String(), nullable=False),
            sa.Column("asin", sa.String(), nullable=False),
            sa.Column("validated_intents", sa.Text(), nullable=True),
            sa.Column("failed_intents", sa.Text(), nullable=True),
            sa.Column("current_main_bottleneck", sa.Text(), nullable=True),
            sa.Column("current_listing_gap", sa.Text(), nullable=True),
            sa.Column("current_traffic_problem", sa.Text(), nullable=True),
            sa.Column("next_best_hypothesis", sa.Text(), nullable=True),
            sa.Column("proven_actions", sa.Text(), nullable=True),
            sa.Column("failed_actions", sa.Text(), nullable=True),
            sa.Column("latest_learning", sa.Text(), nullable=True),
            sa.Column("data_source", sa.String(), nullable=True),
            sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("seller_id", "store_id", "marketplace", "asin", name="uq_asin_ai_memory_scope"),
        )

    inspector = inspect(op.get_bind())
    for table_name, indexes in {
        "report_row_staging": [
            ("ix_report_row_staging_extracted", ["extracted_asin", "extracted_sku"]),
            ("ix_report_row_staging_entity", ["campaign_id", "ad_group_id", "ad_id"]),
            ("ix_report_row_staging_resolution", ["resolution_status", "is_writable"]),
        ],
        "validation_tasks": [("ix_validation_task_intent_decision", ["intent_decision_id"])],
        "asin_execution_logs": [("ix_asin_execution_log_intent_decision", ["intent_decision_id"])],
        "ad_search_term_daily": [("ix_ad_search_term_daily_period", ["period_start", "period_end"])],
        "ad_target_daily": [("ix_ad_target_daily_period", ["period_start", "period_end"])],
        "asin_listing_snapshots": [
            ("ix_asin_listing_snapshot_scope", ["seller_id", "store_id", "marketplace", "asin", "snapshot_at"]),
        ],
        "asin_intent_decisions": [
            ("ix_asin_intent_decision_scope", ["seller_id", "store_id", "marketplace", "asin"]),
            ("ix_asin_intent_decision_status", ["status", "recommended_action"]),
        ],
        "asin_intent_evidence": [
            ("ix_asin_intent_evidence_scope", ["seller_id", "store_id", "marketplace", "asin"]),
            ("ix_asin_intent_evidence_decision", ["intent_decision_id", "source_type"]),
        ],
        "asin_safe_expressions": [
            ("ix_asin_safe_expression_scope", ["seller_id", "store_id", "marketplace", "asin"]),
            ("ix_asin_safe_expression_decision", ["intent_decision_id", "status"]),
        ],
        "asin_ai_memory": [("ix_asin_ai_memory_scope", ["seller_id", "store_id", "marketplace", "asin"])],
    }.items():
        for index_name, columns in indexes:
            _create_index_if_missing(inspector, table_name, index_name, columns)


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    for table_name in (
        "asin_ai_memory",
        "asin_safe_expressions",
        "asin_intent_evidence",
        "asin_intent_decisions",
        "asin_listing_snapshots",
    ):
        if _has_table(inspector, table_name):
            op.drop_table(table_name)
