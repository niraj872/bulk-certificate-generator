from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models import Certificate, CertificateStatus

router = APIRouter(prefix="/certificates", tags=["Certificates"])
settings = get_settings()


@router.get(
    "/{certificate_id}/download",
    summary="Download a generated certificate PDF",
    response_class=FileResponse,
)
def download_certificate(certificate_id: UUID, db: Session = Depends(get_db)) -> FileResponse:
    certificate = db.get(Certificate, str(certificate_id))
    if not certificate:
        raise HTTPException(status_code=404, detail="Certificate not found")
    if certificate.status != CertificateStatus.SUCCESS:
        raise HTTPException(status_code=409, detail="Certificate has not been successfully generated")
    if not certificate.file_path:
        raise HTTPException(status_code=404, detail="Certificate file is missing")

    storage_root = Path(settings.storage_path).resolve()
    file_path = Path(certificate.file_path).resolve()
    try:
        file_path.relative_to(storage_root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Certificate file is unavailable") from exc
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Certificate file is missing")

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=f"certificate-{certificate.id}.pdf",
    )
