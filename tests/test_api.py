from uuid import uuid4


def valid_payload():
    return {
        "certificate_title": "Certificate of Participation",
        "event_name": "AI Workshop 2026",
        "date": "2026-10-06",
        "issuer_name": "ABC Organization",
        "recipients": [
            {"name": "Niraj Kumar Yadav", "email": "niraj@example.com"},
            {"name": "Rahul Kumar", "email": "rahul@example.com"},
        ],
    }


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_generation_job(client):
    response = client.post("/api/v1/jobs", json=valid_payload())
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "PENDING"
    assert body["total_recipients"] == 2
    assert body["job_id"]


def test_invalid_email(client):
    payload = valid_payload()
    payload["recipients"][0]["email"] = "not-an-email"
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 422


def test_empty_recipient_list(client):
    payload = valid_payload()
    payload["recipients"] = []
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 422


def test_missing_job(client):
    response = client.get(f"/api/v1/jobs/{uuid4()}")
    assert response.status_code == 404


def test_job_status_progress_after_processing(client, db):
    from app.models import Certificate, GenerationJob
    from app.workers.worker import process_job

    response = client.post("/api/v1/jobs", json=valid_payload())
    job_id = response.json()["job_id"]
    process_job(job_id)

    response = client.get(f"/api/v1/jobs/{job_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["successful_count"] == 2
    assert body["failed_count"] == 0
    assert body["pending_count"] == 0
    assert body["processing_count"] == 0
    assert body["progress_percentage"] == 100.0


def test_certificate_list(client):
    response = client.post("/api/v1/jobs", json=valid_payload())
    job_id = response.json()["job_id"]
    response = client.get(f"/api/v1/jobs/{job_id}/certificates")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert len(body["certificates"]) == 2
    assert {item["status"] for item in body["certificates"]} == {"PENDING"}


def test_missing_certificate(client):
    response = client.get(f"/api/v1/certificates/{uuid4()}/download")
    assert response.status_code == 404
