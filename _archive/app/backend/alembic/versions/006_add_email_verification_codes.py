"""Add email verification codes.

Revision ID: 006_add_email_codes
Revises: 005_add_timeline_user_id
Create Date: 2026-05-26
"""

from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "006_add_email_codes"
down_revision: Union[str, None] = "005_add_timeline_user_id"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    if "email_verification_codes" in inspector.get_table_names():
        return

    op.create_table(
        "email_verification_codes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("code_hash", sa.String(), nullable=False),
        sa.Column("purpose", sa.String(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_email_verification_codes_id"), "email_verification_codes", ["id"], unique=False)
    op.create_index(op.f("ix_email_verification_codes_email"), "email_verification_codes", ["email"], unique=False)


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    if "email_verification_codes" not in inspector.get_table_names():
        return

    indexes = {index["name"] for index in inspector.get_indexes("email_verification_codes")}
    if "ix_email_verification_codes_email" in indexes:
        op.drop_index(op.f("ix_email_verification_codes_email"), table_name="email_verification_codes")
    if "ix_email_verification_codes_id" in indexes:
        op.drop_index(op.f("ix_email_verification_codes_id"), table_name="email_verification_codes")
    op.drop_table("email_verification_codes")
