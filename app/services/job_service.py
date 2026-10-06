from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Certificate, CertificateStatus, GenerationJob, JobStatus
from app.schemas.job import CreateJobRequest


def create_job(db: Session, request: CreateJobRequest) -> GenerationJob:
    job_id = str(uuid4())
    job = GenerationJob(
        id=job_id,
        status=JobStatus.PENDING,
        certificate_title=request.certificate_title,
        event_name=request.event_name,
        certificate_date=request.date,
        issuer_name=request.issuer_name,
        total_count=len(request.recipients),
        success_count=0,
        failed_count=0,
    )
    db.add(job)
    for recipient in request.recipients:
        db.add(
            Certificate(
                id=str(uuid4()),
                job_id=job_id,
                recipient_name=recipient.name,
                recipient_email=str(recipient.email),
                status=CertificateStatus.PENDING,
            )
        )
    db.commit()
    db.refresh(job)
    return job


def get_job(db: Session, job_id: str) -> GenerationJob | None:
    return db.get(GenerationJob, job_id)


def get_job_counts(db: Session, job_id: str) -> dict[str, int]:
    rows = db.execute(
        select(Certificate.status, func.count(Certificate.id))
        .where(Certificate.job_id == job_id)
        .group_by(Certificate.status)
    ).all()
    counts = {status.value if hasattr(status, "value") else status: count for status, count in rows}
    return {
        "success": counts.get(CertificateStatus.SUCCESS.value, 0),
        "failed": counts.get(CertificateStatus.FAILED.value, 0),
        "pending": counts.get(CertificateStatus.PENDING.value, 0),
        "processing": counts.get(CertificateStatus.PROCESSING.value, 0),
    }


def progress_percentage(total: int, success: int, failed: int) -> float:
    if total == 0:
        return 100.0
    return round(((success + failed) / total) * 100, 2)
