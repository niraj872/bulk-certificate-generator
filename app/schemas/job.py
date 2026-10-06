from datetime import date, datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class JobStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"
    FAILED = "FAILED"


class CertificateStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class RecipientInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("name must not be empty")
        return value


class CreateJobRequest(BaseModel):
    certificate_title: str = Field(min_length=1, max_length=200)
    event_name: str = Field(min_length=1, max_length=300)
    date: date
    issuer_name: str | None = Field(default=None, max_length=200)
    recipients: list[RecipientInput] = Field(min_length=1)

    @field_validator("certificate_title", "event_name", "issuer_name")
    @classmethod
    def validate_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = " ".join(value.split())
        if not value:
            raise ValueError("value must not be empty")
        return value


class JobCreateResponse(BaseModel):
    job_id: UUID
    status: JobStatus
    total_recipients: int
    message: str


class JobStatusResponse(BaseModel):
    job_id: UUID
    status: JobStatus
    total_recipients: int
    successful_count: int
    failed_count: int
    pending_count: int
    processing_count: int
    progress_percentage: float
    created_at: datetime
    completed_at: datetime | None


class CertificateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    certificate_id: UUID = Field(validation_alias="id")
    recipient_name: str
    recipient_email: EmailStr
    status: CertificateStatus
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None


class CertificateListResponse(BaseModel):
    job_id: UUID
    certificates: list[CertificateResponse]
    total: int
