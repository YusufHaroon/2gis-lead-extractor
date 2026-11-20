"""Pydantic request/response models."""
from enum import Enum

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobCreate(BaseModel):
    category: str = Field(min_length=1, max_length=100)
    location: str = Field(min_length=1, max_length=100)
    max_results: int | None = Field(default=None, ge=1)
    source: str | None = None


class BusinessRecord(BaseModel):
    business_name: str
    phone_number: str | None = None


class JobInfo(BaseModel):
    job_id: str
    status: JobStatus
    collected: int = 0
    total_expected: int | None = None
    export_allowed: bool = False
    error: str | None = None
