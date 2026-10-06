from datetime import datetime
from enum import Enum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CertificateStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class Certificate(Base):
    __tablename__ = "certificates"
    __table_args__ = (
        CheckConstraint("length(recipient_name) > 0", name="ck_certificates_recipient_name_nonempty"),
        Index("ix_certificates_job_status", "job_id", "status"),
        Index("ix_certificates_job_created", "job_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recipient_name: Mapped[str] = mapped_column(String(200), nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(320), nullable=False)
    status: Mapped[CertificateStatus] = mapped_column(String(32), nullable=False, index=True)
    file_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    job = relationship("GenerationJob", back_populates="certificates")
