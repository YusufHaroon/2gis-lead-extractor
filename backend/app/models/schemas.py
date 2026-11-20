"""Pydantic request/response models."""
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

# Trimmed before length checks, so whitespace-only input is rejected.
SearchText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class JobStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobCreate(BaseModel):
    category: SearchText
    location: SearchText
    max_results: int | None = Field(default=None, ge=1)  # clamped to MAX_RESULTS_CAP server-side
    source: str | None = Field(default=None, max_length=50)


class BusinessRecord(BaseModel):
    business_name: str
    phone_number: str | None = None
    address: str | None = None
    category: str | None = None
    opening_hours: str | None = None


class JobInfo(BaseModel):
    job_id: str
    status: JobStatus
    collected: int = 0
    total_expected: int | None = None
    export_allowed: bool = False
    error: str | None = None


class SourceInfo(BaseModel):
    name: str
    label: str
    enabled: bool
    export_allowed: bool
    is_default: bool
