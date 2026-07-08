"""Stage 4 models migration

Revision ID: 0001_stage4_models
Revises: 
Create Date: 2026-07-03
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0001_stage4_models"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Residents
    op.create_table(
        "residents",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("apartment_id", sa.Uuid(), sa.ForeignKey("apartments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("floor_id", sa.Uuid(), sa.ForeignKey("floors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("flat_id", sa.Uuid(), sa.ForeignKey("flats.id", ondelete="CASCADE"), nullable=False),
        sa.Column("booking_id", sa.Uuid(), sa.ForeignKey("bookings.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resident_type", sa.String(20), nullable=False),
        sa.Column("move_in_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="Active"),
        sa.Column("agreement_number", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # Maintenance bills
    op.create_table(
        "maintenance_bills",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("resident_id", sa.Uuid(), sa.ForeignKey("residents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("flat_id", sa.Uuid(), sa.ForeignKey("flats.id", ondelete="CASCADE"), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("late_fee", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("payment_status", sa.String(20), nullable=False, server_default="Pending"),
        sa.Column("payment_date", sa.DateTime(), nullable=True),
        sa.Column("razorpay_payment_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # Rent records
    op.create_table(
        "rent_records",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("resident_id", sa.Uuid(), sa.ForeignKey("residents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("flat_id", sa.Uuid(), sa.ForeignKey("flats.id", ondelete="CASCADE"), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("payment_status", sa.String(20), nullable=False, server_default="Pending"),
        sa.Column("payment_date", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # Community rules
    op.create_table(
        "community_rules",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("apartment_id", sa.Uuid(), sa.ForeignKey("apartments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(100), nullable=False, server_default="General"),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("community_rules")
    op.drop_table("rent_records")
    op.drop_table("maintenance_bills")
    op.drop_table("residents")
