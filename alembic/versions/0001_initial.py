"""create certificate generation tables

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "generation_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("certificate_title", sa.String(length=200), nullable=False),
        sa.Column("event_name", sa.String(length=300), nullable=False),
        sa.Column("certificate_date", sa.Date(), nullable=False),
        sa.Column("issuer_name", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("total_count", sa.Integer(), nullable=False),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("total_count > 0", name="ck_generation_jobs_total_positive"),
        sa.CheckConstraint("success_count >= 0", name="ck_generation_jobs_success_nonnegative"),
        sa.CheckConstraint("failed_count >= 0", name="ck_generation_jobs_failed_nonnegative"),
    )
    op.create_index("ix_generation_jobs_status", "generation_jobs", ["status"])

    op.create_table(
        "certificates",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("job_id", sa.String(length=36), sa.ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recipient_name", sa.String(length=200), nullable=False),
        sa.Column("recipient_email", sa.String(length=320), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("file_path", sa.String(length=1000), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("length(recipient_name) > 0", name="ck_certificates_recipient_name_nonempty"),
    )
    op.create_index("ix_certificates_job_id", "certificates", ["job_id"])
    op.create_index("ix_certificates_status", "certificates", ["status"])
    op.create_index("ix_certificates_job_status", "certificates", ["job_id", "status"])
    op.create_index("ix_certificates_job_created", "certificates", ["job_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_certificates_job_created", table_name="certificates")
    op.drop_index("ix_certificates_job_status", table_name="certificates")
    op.drop_index("ix_certificates_status", table_name="certificates")
    op.drop_index("ix_certificates_job_id", table_name="certificates")
    op.drop_table("certificates")
    op.drop_index("ix_generation_jobs_status", table_name="generation_jobs")
    op.drop_table("generation_jobs")
