from pathlib import Path

from app.models import Certificate, CertificateStatus
from app.services.job_service import create_job
from app.workers import worker
from tests.test_api import valid_payload


def create_db_job(db):
    from app.schemas.job import CreateJobRequest
    return create_job(db, CreateJobRequest.model_validate(valid_payload()))


def test_certificate_generation_creates_pdf(db):
    job = create_db_job(db)
    worker.process_job(job.id)
    certificates = db.query(Certificate).filter(Certificate.job_id == job.id).all()
    assert len(certificates) == 2
    assert all(c.status == CertificateStatus.SUCCESS for c in certificates)
    assert all(c.file_path and Path(c.file_path).is_file() for c in certificates)


def test_successful_certificate_retrieval(client):
    response = client.post("/api/v1/jobs", json=valid_payload())
    job_id = response.json()["job_id"]
    worker.process_job(job_id)
    certificates = client.get(f"/api/v1/jobs/{job_id}/certificates").json()["certificates"]
    certificate_id = certificates[0]["certificate_id"]
    response = client.get(f"/api/v1/certificates/{certificate_id}/download")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_download_before_success_returns_conflict(client):
    response = client.post("/api/v1/jobs", json=valid_payload())
    job_id = response.json()["job_id"]
    certificate_id = client.get(f"/api/v1/jobs/{job_id}/certificates").json()["certificates"][0]["certificate_id"]
    response = client.get(f"/api/v1/certificates/{certificate_id}/download")
    assert response.status_code == 409


def test_individual_failure_does_not_stop_batch(db, monkeypatch):
    job = create_db_job(db)
    original = worker.generate_certificate_pdf

    def fail_first(*, output_path, recipient_name, **kwargs):
        if recipient_name == "Niraj Kumar Yadav":
            raise RuntimeError("simulated PDF failure")
        return original(output_path=output_path, recipient_name=recipient_name, **kwargs)

    monkeypatch.setattr(worker, "generate_certificate_pdf", fail_first)
    worker.process_job(job.id)

    certificates = db.query(Certificate).filter(Certificate.job_id == job.id).all()
    statuses = {c.recipient_name: c.status for c in certificates}
    errors = {c.recipient_name: c.error_message for c in certificates}
    assert statuses["Niraj Kumar Yadav"] == CertificateStatus.FAILED
    assert errors["Niraj Kumar Yadav"]
    assert statuses["Rahul Kumar"] == CertificateStatus.SUCCESS

    db.refresh(job)
    assert job.status == "COMPLETED_WITH_ERRORS"
    assert job.success_count == 1
    assert job.failed_count == 1


def test_progress_formula():
    from app.services.job_service import progress_percentage
    assert progress_percentage(100, 98, 2) == 100.0
    assert progress_percentage(100, 50, 0) == 50.0
    assert progress_percentage(3, 1, 1) == 66.67
