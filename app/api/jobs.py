from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

import logging

from app.core.config import get_settings
from app.db.session import get_db
from app.models import Certificate, GenerationJob
from app.schemas.job import CertificateListResponse, CreateJobRequest, JobCreateResponse, JobStatusResponse
from app.services.job_service import create_job, get_job, get_job_counts, progress_percentage

router = APIRouter(prefix="/jobs", tags=["Jobs"])
settings = get_settings()
logger = logging.getLogger(__name__)


@router.post(
    "",
    response_model=JobCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create a bulk certificate generation job",
    description="Creates one persisted job and one certificate record per recipient. A separate worker generates the PDFs.",
)
def create_generation_job(request: CreateJobRequest, db: Session = Depends(get_db)) -> JobCreateResponse:
    if len(request.recipients) > settings.max_recipients:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"recipient count cannot exceed {settings.max_recipients}",
        )
    try:
        job = create_job(db, request)
    except Exception as exc:
        db.rollback()
        logger.exception("Unable to create generation job")
        raise HTTPException(status_code=503, detail="Unable to create generation job") from exc
    return JobCreateResponse(
        job_id=UUID(job.id),
        status=job.status,
        total_recipients=job.total_count,
        message="Generation job accepted for background processing",
    )


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    summary="Get generation job status",
)
def get_generation_job(job_id: UUID, db: Session = Depends(get_db)) -> JobStatusResponse:
    job = get_job(db, str(job_id))
    if not job:
        raise HTTPException(status_code=404, detail="Generation job not found")
    counts = get_job_counts(db, job.id)
    return JobStatusResponse(
        job_id=job_id,
        status=job.status,
        total_recipients=job.total_count,
        successful_count=counts["success"],
        failed_count=counts["failed"],
        pending_count=counts["pending"],
        processing_count=counts["processing"],
        progress_percentage=progress_percentage(job.total_count, counts["success"], counts["failed"]),
        created_at=job.created_at,
        completed_at=job.completed_at,
    )


@router.get(
    "/{job_id}/certificates",
    response_model=CertificateListResponse,
    summary="List certificates for a generation job",
)
def list_certificates(job_id: UUID, db: Session = Depends(get_db)) -> CertificateListResponse:
    if not get_job(db, str(job_id)):
        raise HTTPException(status_code=404, detail="Generation job not found")
    certificates = db.scalars(
        select(Certificate)
        .where(Certificate.job_id == str(job_id))
        .order_by(Certificate.created_at, Certificate.id)
    ).all()
    return CertificateListResponse(job_id=job_id, certificates=certificates, total=len(certificates))
