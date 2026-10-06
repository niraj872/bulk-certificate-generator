import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select, update

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Certificate, CertificateStatus, GenerationJob, JobStatus
from app.pdf.certificate import generate_certificate_pdf
from app.services.job_service import get_job_counts

logger = logging.getLogger(__name__)
settings = get_settings()


def claim_job() -> str | None:
    """Atomically claim one pending/stale job; returns its id."""
    with SessionLocal.begin() as db:
        now = datetime.now(timezone.utc)
        stale_before = now - timedelta(seconds=settings.job_stale_seconds)

        stale_ids = db.scalars(
            select(GenerationJob.id)
            .where(
                GenerationJob.status == JobStatus.PROCESSING,
                GenerationJob.created_at < stale_before,
            )
            .with_for_update(skip_locked=True)
            .limit(20)
        ).all()
        if stale_ids:
            db.execute(
                update(GenerationJob)
                .where(GenerationJob.id.in_(stale_ids))
                .values(status=JobStatus.PENDING, completed_at=None)
            )

        job = db.scalars(
            select(GenerationJob)
            .where(GenerationJob.status == JobStatus.PENDING)
            .order_by(GenerationJob.created_at)
            .with_for_update(skip_locked=True)
        ).first()
        if not job:
            return None
        job.status = JobStatus.PROCESSING
        return job.id


def process_job(job_id: str) -> None:
    settings.storage_path and Path(settings.storage_path).mkdir(parents=True, exist_ok=True)

    with SessionLocal() as db:
        job = db.get(GenerationJob, job_id)
        if not job:
            logger.error("Claimed job %s no longer exists", job_id)
            return

        certificate_ids = db.scalars(
            select(Certificate.id)
            .where(
                Certificate.job_id == job_id,
                Certificate.status.in_([CertificateStatus.PENDING, CertificateStatus.PROCESSING]),
            )
            .order_by(Certificate.created_at)
        ).all()

    for certificate_id in certificate_ids:
        process_certificate(job_id, certificate_id)

    with SessionLocal.begin() as db:
        job = db.get(GenerationJob, job_id)
        if not job:
            return
        counts = get_job_counts(db, job_id)
        job.success_count = counts["success"]
        job.failed_count = counts["failed"]
        if counts["success"] + counts["failed"] == job.total_count:
            job.status = (
                JobStatus.COMPLETED_WITH_ERRORS if counts["failed"] else JobStatus.COMPLETED
            )
            job.completed_at = datetime.now(timezone.utc)
        else:
            job.status = JobStatus.FAILED
            job.completed_at = datetime.now(timezone.utc)


def process_certificate(job_id: str, certificate_id: str) -> None:
    with SessionLocal.begin() as db:
        certificate = db.get(Certificate, certificate_id)
        job = db.get(GenerationJob, job_id)
        if not certificate or not job or certificate.job_id != job_id:
            return
        if certificate.status == CertificateStatus.SUCCESS:
            return
        certificate.status = CertificateStatus.PROCESSING
        certificate.error_message = None

    try:
        safe_filename = f"{certificate_id}.pdf"
        output_path = Path(settings.storage_path) / job_id / safe_filename
        generate_certificate_pdf(
            output_path=output_path,
            certificate_title=job.certificate_title,
            event_name=job.event_name,
            certificate_date=job.certificate_date,
            issuer_name=job.issuer_name,
            recipient_name=certificate.recipient_name,
        )
        with SessionLocal.begin() as db:
            certificate = db.get(Certificate, certificate_id)
            if certificate:
                certificate.status = CertificateStatus.SUCCESS
                certificate.file_path = str(output_path.resolve())
                certificate.completed_at = datetime.now(timezone.utc)
    except Exception as exc:  # individual failure must not stop the batch
        logger.exception("Certificate generation failed for certificate_id=%s", certificate_id)
        with SessionLocal.begin() as db:
            certificate = db.get(Certificate, certificate_id)
            if certificate:
                certificate.status = CertificateStatus.FAILED
                certificate.error_message = f"Certificate generation failed: {type(exc).__name__}"
                certificate.completed_at = datetime.now(timezone.utc)


def run_worker() -> None:
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    logger.info("Certificate worker started")
    while True:
        try:
            job_id = claim_job()
            if job_id:
                logger.info("Processing job %s", job_id)
                process_job(job_id)
            else:
                time.sleep(settings.worker_poll_seconds)
        except Exception:
            logger.exception("Worker loop failed; retrying")
            time.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    run_worker()
