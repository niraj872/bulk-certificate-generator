# Bulk Certificate Generator API

A clean, interview-ready FastAPI backend for generating many individual certificate PDFs from one predefined template.

## Project overview

The API accepts one generation request containing certificate metadata and a list of recipients. It creates one persisted **generation job** and one **certificate row per recipient**, immediately returns a `job_id`, and lets a separate worker generate PDFs in the background.

The design intentionally avoids Redis/Celery. PostgreSQL acts as the durable job queue: the worker claims pending jobs using row locking, and completed certificate state is stored in the database.

## Features

- FastAPI + OpenAPI (`/docs`, `/redoc`)
- PostgreSQL + SQLAlchemy 2
- Alembic migrations
- Pydantic request/response validation
- One professional predefined ReportLab certificate template
- Bulk requests with configurable recipient limit
- Durable background worker without Redis/Celery
- Per-certificate success/failure tracking
- Progress and job status tracking
- Safe UUID-based file names
- Path traversal protection on downloads
- Docker Compose with API, worker, and PostgreSQL
- Pytest coverage for required API and generation scenarios
- Structured application logging without logging recipient PII

## Architecture

```text
Client
  |
  | POST /api/v1/jobs
  v
FastAPI API
  |
  | transaction: job + certificate rows
  v
PostgreSQL  <---------------------------+
  |                                     |
  | PENDING                             | status/file updates
  v                                     |
Certificate Worker ---------------------+
  |
  | ReportLab
  v
/app/storage/{job_id}/{certificate_id}.pdf
  |
  | GET /api/v1/certificates/{id}/download
  v
Client
```

### Why a database-backed worker?

For this assignment, a dedicated Python worker polling PostgreSQL is simpler to understand than introducing Redis and Celery. Jobs are durable because they live in PostgreSQL. A worker restart does not lose queued jobs. Row-level locking with `FOR UPDATE SKIP LOCKED` prevents two workers from claiming the same pending job.

This is intentionally an assignment-sized architecture, not a claim that PostgreSQL polling is the best queue for every production workload.

## Database design

### `generation_jobs`

- `id` - UUID string primary key
- `certificate_title`
- `event_name`
- `certificate_date`
- `issuer_name`
- `status`
- `total_count`
- `success_count`
- `failed_count`
- `created_at`
- `completed_at`

The job stores all template inputs needed by the worker. This is important because the original HTTP request is not available after the API returns.

### `certificates`

- `id` - UUID string primary key
- `job_id` - foreign key to `generation_jobs`
- `recipient_name`
- `recipient_email`
- `status`
- `file_path`
- `error_message`
- `created_at`
- `completed_at`

Indexes support job lookup, status counting, and ordered certificate listing.

## Status model

### Job

- `PENDING` - queued but not claimed
- `PROCESSING` - worker is processing the batch
- `COMPLETED` - all certificates succeeded
- `COMPLETED_WITH_ERRORS` - all certificates finished but at least one failed
- `FAILED` - unexpected batch-level condition prevented completion

### Certificate

- `PENDING`
- `PROCESSING`
- `SUCCESS`
- `FAILED`

## Progress calculation

Progress is based on certificates that have reached a terminal state:

```text
progress = ((successful + failed) / total) * 100
```

For example, 98 successful + 2 failed out of 100 is 100% progress and `COMPLETED_WITH_ERRORS`.

## Individual failure handling

Each recipient is processed independently inside `process_certificate()`. PDF generation is wrapped in its own `try/except`. A failure changes only that certificate to `FAILED` and stores a safe error description. The worker continues with the next certificate.

The API never exposes a Python traceback to the client.

## Background processing and restart behavior

The API only creates the job and certificate records. The worker does the PDF work.

If the worker stops before claiming a job, the job remains `PENDING`. If a worker crashes after claiming a job, the worker's next run can recover stale `PROCESSING` jobs after `JOB_STALE_SECONDS`. Already-successful certificates are skipped, so retries do not intentionally overwrite successful records.

For a multi-worker deployment, PostgreSQL row locking is the coordination mechanism. A future implementation could move the same processing functions behind Celery/RQ/SQS without changing the API contract.

## Preventing duplicate processing

`SELECT ... FOR UPDATE SKIP LOCKED` is used when claiming a job. Only one worker can claim the same row at a time. A certificate already marked `SUCCESS` is skipped during retry.

The file name is based on the certificate UUID, not recipient input, so names cannot cause path traversal or file collisions.

## Transactions

Creating a job and all certificate rows is one database transaction. If that transaction fails, the API rolls back rather than leaving a half-created job.

Individual certificate status/file updates are committed separately so one PDF failure cannot roll back successful certificates from the same batch.

## Security/basic quality

- Pydantic validates dates, required fields, names, and emails.
- Recipient count is capped by `MAX_RECIPIENTS`.
- Secrets/configuration come from environment variables.
- File names are server-generated UUIDs.
- Download paths must resolve underneath the configured storage directory.
- API errors do not expose stack traces.
- CORS is explicitly configured.
- Logs contain IDs and operational information, not recipient names/emails.

Authentication is intentionally omitted because it is not required by the assignment.

## Technology stack

- Python 3.12+
- FastAPI
- Pydantic v2
- SQLAlchemy 2
- PostgreSQL 16
- Alembic
- ReportLab
- Pytest
- Docker Compose

## Project structure

```text
bulk-certificate-generator/
├── app/
│   ├── api/
│   │   ├── certificates.py
│   │   ├── health.py
│   │   └── jobs.py
│   ├── core/
│   │   ├── config.py
│   │   └── logging.py
│   ├── db/
│   │   ├── base.py
│   │   └── session.py
│   ├── models/
│   │   ├── certificate.py
│   │   └── job.py
│   ├── pdf/
│   │   └── certificate.py
│   ├── schemas/
│   │   └── job.py
│   ├── services/
│   │   └── job_service.py
│   ├── workers/
│   │   └── worker.py
│   └── main.py
├── alembic/
│   ├── versions/0001_initial.py
│   └── env.py
├── tests/
├── storage/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

## Prerequisites

Local development:

- Python 3.12+
- PostgreSQL 16+
- pip

Docker development:

- Docker Desktop with Compose

## Local setup

```bash
git clone <your-repository-url>
cd bulk-certificate-generator
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and change `DATABASE_URL` to your local PostgreSQL connection string.

Example:

```env
DATABASE_URL=postgresql+psycopg://certificates:certificates@localhost:5432/certificates
STORAGE_PATH=./storage
MAX_RECIPIENTS=1000
WORKER_POLL_SECONDS=2
JOB_STALE_SECONDS=300
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
LOG_LEVEL=INFO
```

Create/update the schema:

```bash
alembic upgrade head
```

Start the API:

```bash
uvicorn app.main:app --reload
```

In a second terminal, start the worker:

```bash
python -m app.workers.worker
```

## Docker setup

Build and start everything:

```bash
docker compose up --build
```

The API runs at `http://localhost:8000`.

Swagger: `http://localhost:8000/docs`

ReDoc: `http://localhost:8000/redoc`

Stop:

```bash
docker compose down
```

Stop and remove database/storage volumes:

```bash
docker compose down -v
```

The API container runs `alembic upgrade head` before starting FastAPI. The worker shares the certificate storage volume with the API.

## Environment variables

| Variable | Purpose | Example |
|---|---|---|
| `DATABASE_URL` | SQLAlchemy database URL | `postgresql+psycopg://...` |
| `STORAGE_PATH` | Certificate PDF root directory | `./storage` |
| `MAX_RECIPIENTS` | Per-job recipient limit | `1000` |
| `WORKER_POLL_SECONDS` | Worker polling interval | `2` |
| `JOB_STALE_SECONDS` | Time before a claimed job can be recovered | `300` |
| `CORS_ORIGINS` | Comma-separated allowed browser origins | `http://localhost:5173` |
| `LOG_LEVEL` | Application log level | `INFO` |

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Database-backed health check |
| POST | `/api/v1/jobs` | Create bulk generation job |
| GET | `/api/v1/jobs/{job_id}` | Get job status/progress |
| GET | `/api/v1/jobs/{job_id}/certificates` | List certificate records |
| GET | `/api/v1/certificates/{certificate_id}/download` | Download successful PDF |

## Create a job

```bash
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "certificate_title": "Certificate of Participation",
    "event_name": "AI Workshop 2026",
    "date": "2026-10-06",
    "issuer_name": "ABC Organization",
    "recipients": [
      {"name": "Niraj Kumar Yadav", "email": "niraj@example.com"},
      {"name": "Rahul Kumar", "email": "rahul@example.com"}
    ]
  }'
```

Example response:

```json
{
  "job_id": "6f96b8d6-4d37-4b9d-bdd6-3b1c2aef9a53",
  "status": "PENDING",
  "total_recipients": 2,
  "message": "Generation job accepted for background processing"
}
```

The `202 Accepted` response means the request was accepted; PDF generation happens asynchronously.

## Check job progress

```bash
curl http://localhost:8000/api/v1/jobs/6f96b8d6-4d37-4b9d-bdd6-3b1c2aef9a53
```

Example completed response:

```json
{
  "job_id": "6f96b8d6-4d37-4b9d-bdd6-3b1c2aef9a53",
  "status": "COMPLETED",
  "total_recipients": 2,
  "successful_count": 2,
  "failed_count": 0,
  "pending_count": 0,
  "processing_count": 0,
  "progress_percentage": 100.0,
  "created_at": "2026-10-06T16:30:00Z",
  "completed_at": "2026-10-06T16:30:03Z"
}
```

## List certificates

```bash
curl http://localhost:8000/api/v1/jobs/6f96b8d6-4d37-4b9d-bdd6-3b1c2aef9a53/certificates
```

Failed certificates contain an `error_message`; successful certificates have `error_message: null`.

## Download a certificate

```bash
curl -L \
  -o certificate.pdf \
  http://localhost:8000/api/v1/certificates/<certificate_id>/download
```

A certificate that is still pending/processing returns `409`. A missing certificate or missing file returns `404`.

## Validation and error handling

Invalid JSON fields, invalid emails, empty recipient lists, invalid dates, blank names, and over-limit recipient counts are rejected. Typical responses are:

- `202` - job accepted
- `404` - job/certificate/file not found
- `409` - certificate is not ready
- `422` - request validation error
- `503` - database/job creation failure
- `500` - unexpected server error

Internal exception details are logged server-side but not returned to clients.

## Interview design decisions

### Why FastAPI?

It provides strong Pydantic validation, automatic OpenAPI documentation, async-friendly APIs, and very little framework boilerplate. The assignment's API is mostly I/O and job submission, which fits FastAPI well.

### Why PostgreSQL?

The assignment explicitly asks for PostgreSQL, and it is a reliable transactional store for job state, certificate metadata, and worker coordination.

### Why background processing?

PDF creation is potentially slow for hundreds of recipients. Returning a `job_id` quickly keeps the HTTP request bounded and lets clients poll progress.

### Why this schema?

A job represents one bulk request, while certificates represent independently trackable work items. The foreign key makes ownership explicit and supports progress queries.

### How is progress calculated?

`(SUCCESS + FAILED) / TOTAL * 100`. Both successful and failed certificates are terminal, so the batch can be 100% complete even when it has errors.

### How are individual failures handled?

Each certificate has its own transaction and `try/except`. One failure is recorded as `FAILED`, then processing continues.

### What happens if the server restarts?

Queued jobs are in PostgreSQL, not process memory. A claimed stale job can be recovered. Successful certificates remain successful and are skipped on retry.

### How are files stored?

Files are stored under `STORAGE_PATH/<job_id>/<certificate_id>.pdf`. UUID-derived names avoid user-controlled file paths. The download endpoint verifies the resolved path stays below `STORAGE_PATH`.

### How would you scale to 10,000 recipients?

First, keep the API unchanged and move job execution to multiple worker processes/containers. PostgreSQL row locking can distribute jobs. For sustained high throughput, replace the polling queue with SQS/RabbitMQ/Celery/RQ and use object storage such as S3/GCS for PDFs. Batch database writes and add rate/concurrency controls.

### How would you replace the worker with Celery/RQ?

Keep `create_job()` and the database state model. Replace the polling `claim_job()` loop with a queue task that calls the existing `process_job()` function. The API contract does not need to change.

### How do you prevent duplicate processing?

Workers claim jobs under a database row lock. Certificates already marked `SUCCESS` are skipped during recovery.

### How are invalid recipients handled?

Request-level validation rejects malformed recipients before a job is created. Generation-time failures are different: a valid recipient can still fail during PDF creation, and that item is marked `FAILED` without stopping the batch.

### How are transactions handled?

Job + certificate creation is one transaction. Certificate generation/status updates are independent transactions, preventing one PDF error from rolling back the entire batch.

## Testing

Run:

```bash
pytest -q
```

The tests use SQLite for deterministic isolation and speed, while production uses PostgreSQL. They cover health, validation, job creation, progress, PDF generation, download, missing resources, and continuation after an individual failure.

## Limitations / future improvements

- No authentication/authorization because it is outside the assignment.
- Local/shared filesystem storage is used instead of object storage.
- PostgreSQL polling is intentionally simple; high-volume production systems would normally use a dedicated queue.
- No email delivery is implemented because the assignment asks for generation/retrieval, not sending.
- A future deployment could add metrics, distributed tracing, rate limiting, object storage, and a dedicated queue.

## API documentation

FastAPI automatically exposes:

- Swagger UI: `/docs`
- ReDoc: `/redoc`
- OpenAPI JSON: `/openapi.json`

Endpoint summaries and typed request/response models are included in the generated documentation.
