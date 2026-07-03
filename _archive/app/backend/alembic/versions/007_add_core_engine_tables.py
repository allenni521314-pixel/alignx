"""Add core engine tables.

Revision ID: 007_add_core_engine
Revises: 006_add_email_codes
Create Date: 2026-06-03
"""

from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "007_add_core_engine"
down_revision: Union[str, None] = "006_add_email_codes"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def _create_index_if_missing(inspector, table_name: str, index_name: str, columns: list[str]) -> None:
    indexes = {index["name"] for index in inspector.get_indexes(table_name)}
    if index_name not in indexes:
        op.create_index(index_name, table_name, columns, unique=False)


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    if "human_nature_graph_nodes" not in tables:
        op.create_table(
            "human_nature_graph_nodes",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("node_type", sa.String(), nullable=False),
            sa.Column("layer", sa.String(), nullable=False),
            sa.Column("parent_ids", sa.Text(), nullable=True),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
            sa.Column("evidence_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("evidence_quality", sa.Float(), nullable=False, server_default="0"),
            sa.Column("time_decay", sa.Float(), nullable=False, server_default="1"),
            sa.Column("attributes", sa.Text(), nullable=True),
            sa.Column("created_by", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
        )
    if "human_nature_graph_edges" not in tables:
        op.create_table(
            "human_nature_graph_edges",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("from_node_id", sa.String(), nullable=False),
            sa.Column("to_node_id", sa.String(), nullable=False),
            sa.Column("relation_type", sa.String(), nullable=False),
            sa.Column("weight", sa.Float(), nullable=False, server_default="0"),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
            sa.Column("evidence_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("evidence_quality", sa.Float(), nullable=False, server_default="0"),
            sa.Column("time_decay", sa.Float(), nullable=False, server_default="1"),
            sa.Column("evidence_sources", sa.Text(), nullable=True),
            sa.Column("attributes", sa.Text(), nullable=True),
            sa.Column("created_by", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
        )
    if "core_engine_evidence" not in tables:
        op.create_table(
            "core_engine_evidence",
            sa.Column("evidence_id", sa.String(), nullable=False),
            sa.Column("source_type", sa.String(), nullable=True),
            sa.Column("source_id", sa.String(), nullable=True),
            sa.Column("graph_node_ids", sa.Text(), nullable=True),
            sa.Column("graph_edge_ids", sa.Text(), nullable=True),
            sa.Column("metrics", sa.Text(), nullable=True),
            sa.Column("evidence_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("evidence_quality", sa.Float(), nullable=False, server_default="0"),
            sa.Column("sample_size", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("conversion_signal", sa.Float(), nullable=False, server_default="0"),
            sa.Column("consistency", sa.Float(), nullable=False, server_default="0"),
            sa.Column("statistical_confidence", sa.Float(), nullable=False, server_default="0"),
            sa.Column("proof_score", sa.Float(), nullable=False, server_default="0"),
            sa.Column("proof_state", sa.String(), nullable=False),
            sa.Column("created_by", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("evidence_id"),
        )
    if "capital_allocation_records" not in tables:
        op.create_table(
            "capital_allocation_records",
            sa.Column("allocation_id", sa.String(), nullable=False),
            sa.Column("opportunity_id", sa.String(), nullable=False),
            sa.Column("evidence_id", sa.String(), nullable=True),
            sa.Column("graph_node_ids", sa.Text(), nullable=True),
            sa.Column("graph_edge_ids", sa.Text(), nullable=True),
            sa.Column("opportunity_score", sa.Float(), nullable=False, server_default="0"),
            sa.Column("proof_score", sa.Float(), nullable=False, server_default="0"),
            sa.Column("risk_score", sa.Float(), nullable=False, server_default="0"),
            sa.Column("information_gain", sa.Float(), nullable=False, server_default="0"),
            sa.Column("priority_score", sa.Float(), nullable=False, server_default="0"),
            sa.Column("suggested_action", sa.String(), nullable=False),
            sa.Column("budget", sa.Float(), nullable=False, server_default="0"),
            sa.Column("suggested_budget", sa.Float(), nullable=False, server_default="0"),
            sa.Column("requires_human_confirmation", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_by", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("allocation_id"),
        )
    if "knowledge_evolution_events" not in tables:
        op.create_table(
            "knowledge_evolution_events",
            sa.Column("event_id", sa.String(), nullable=False),
            sa.Column("evidence_id", sa.String(), nullable=True),
            sa.Column("node_id", sa.String(), nullable=True),
            sa.Column("edge_id", sa.String(), nullable=True),
            sa.Column("event_type", sa.String(), nullable=False),
            sa.Column("previous_weight", sa.Float(), nullable=False, server_default="0"),
            sa.Column("new_weight", sa.Float(), nullable=False, server_default="0"),
            sa.Column("previous_confidence", sa.Float(), nullable=False, server_default="0"),
            sa.Column("new_confidence", sa.Float(), nullable=False, server_default="0"),
            sa.Column("reason", sa.String(), nullable=False, server_default="未设置"),
            sa.Column("created_by", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("event_id"),
        )

    inspector = inspect(op.get_bind())
    for table_name, indexes in {
        "human_nature_graph_nodes": [
            ("ix_human_nature_graph_nodes_name", ["name"]),
            ("ix_human_nature_graph_nodes_node_type", ["node_type"]),
            ("ix_human_nature_graph_nodes_layer", ["layer"]),
            ("ix_human_nature_graph_nodes_created_by", ["created_by"]),
        ],
        "human_nature_graph_edges": [
            ("ix_human_nature_graph_edges_from_node_id", ["from_node_id"]),
            ("ix_human_nature_graph_edges_to_node_id", ["to_node_id"]),
            ("ix_human_nature_graph_edges_relation_type", ["relation_type"]),
            ("ix_human_nature_graph_edges_created_by", ["created_by"]),
        ],
        "core_engine_evidence": [
            ("ix_core_engine_evidence_source_type", ["source_type"]),
            ("ix_core_engine_evidence_source_id", ["source_id"]),
            ("ix_core_engine_evidence_proof_state", ["proof_state"]),
            ("ix_core_engine_evidence_created_by", ["created_by"]),
        ],
        "capital_allocation_records": [
            ("ix_capital_allocation_records_opportunity_id", ["opportunity_id"]),
            ("ix_capital_allocation_records_evidence_id", ["evidence_id"]),
            ("ix_capital_allocation_records_suggested_action", ["suggested_action"]),
            ("ix_capital_allocation_records_created_by", ["created_by"]),
        ],
        "knowledge_evolution_events": [
            ("ix_knowledge_evolution_events_evidence_id", ["evidence_id"]),
            ("ix_knowledge_evolution_events_node_id", ["node_id"]),
            ("ix_knowledge_evolution_events_edge_id", ["edge_id"]),
            ("ix_knowledge_evolution_events_event_type", ["event_type"]),
            ("ix_knowledge_evolution_events_created_by", ["created_by"]),
        ],
    }.items():
        _create_index_if_missing(inspector, table_name, *indexes[0])
        for index_name, columns in indexes[1:]:
            _create_index_if_missing(inspector, table_name, index_name, columns)


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    for table_name in (
        "knowledge_evolution_events",
        "capital_allocation_records",
        "core_engine_evidence",
        "human_nature_graph_edges",
        "human_nature_graph_nodes",
    ):
        if table_name in tables:
            op.drop_table(table_name)
