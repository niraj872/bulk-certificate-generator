from datetime import date, datetime
from enum import Enum

from sqlalchemy import CheckConstraint, Date, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class JobStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"
    FAILED = "FAILED"


class GenerationJob(Base):
    __tablename__ = "generation_jobs"
    __table_args__ = (
        CheckConstraint("total_count > 0", name="ck_generation_jobs_total_positive"),
        CheckConstraint("success_count >= 0", name="ck_generation_jobs_success_nonnegative"),
        CheckConstraint("failed_count >= 0", name="ck_generation_jobs_failed_nonnegative"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[JobStatus] = mapped_column(String(32), nullable=False, index=True)
    certificate_title: Mapped[str] = mapped_column(String(200), nullable=False)
    event_name: Mapped[str] = mapped_column(String(300), nullable=False)
    certificate_date: Mapped[date] = mapped_column(Date, nullable=False)
    issuer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    total_count: Mapped[int] = mapped_column(Integer, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    certificates = relationship("Certificate", back_populates="job", cascade="all, delete-orphan")
