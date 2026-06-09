"""Domain models and API schemas (Pydantic).

These match docs/API_CONTRACT.md exactly. Responses are wrapped in an
``Envelope`` by the API layer.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Generic, Literal, Optional, TypeVar
from uuid import uuid4

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid4())


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class JobStatus(str, Enum):
    QUEUED = "queued"
    SCANNING = "scanning"
    SCANNED = "scanned"
    REMEDIATING = "remediating"
    REMEDIATED = "remediated"
    SIGNING = "signing"
    SIGNED = "signed"
    FAILED = "failed"


TERMINAL_STATUSES = {JobStatus.SIGNED, JobStatus.FAILED}


class Vulnerability(BaseModel):
    id: str
    severity: Severity = Severity.UNKNOWN
    package: str = ""
    installed_version: str = ""
    fixed_version: str = ""
    title: str = ""
    sources: list[str] = Field(default_factory=list)


class ScanSummary(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    unknown: int = 0
    total: int = 0

    @classmethod
    def from_vulns(cls, vulns: list[Vulnerability]) -> "ScanSummary":
        s = cls()
        for v in vulns:
            key = v.severity.value.lower()
            setattr(s, key, getattr(s, key) + 1)
        s.total = len(vulns)
        return s


class ScanResult(BaseModel):
    summary: ScanSummary = Field(default_factory=ScanSummary)
    vulnerabilities: list[Vulnerability] = Field(default_factory=list)
    trivy_summary: ScanSummary = Field(default_factory=ScanSummary)
    grype_summary: ScanSummary = Field(default_factory=ScanSummary)
    os_family: str = ""


class RemediationResult(BaseModel):
    new_image: str
    base_image: str
    strategy: str
    remaining: ScanSummary = Field(default_factory=ScanSummary)
    fixed_count: int = 0
    dockerfile: str = ""
    # False when the post-patch re-scan could not run. In that case `remaining`
    # falls back to the original counts and `fixed_count` is 0 — we never claim
    # vulnerabilities were fixed without verifying it.
    rescan_ok: bool = True


class BaseAlternative(BaseModel):
    """A candidate minimal/hardened base image and its vulnerability count."""

    image: str
    available: bool = False
    summary: ScanSummary = Field(default_factory=ScanSummary)
    note: str = ""
    error: str = ""


class SignatureResult(BaseModel):
    signed: bool = False
    reference: str = ""
    key: str = ""
    bundle: str = ""


class LogEntry(BaseModel):
    ts: datetime = Field(default_factory=_now)
    level: Literal["info", "warn", "error"] = "info"
    message: str = ""


class Job(BaseModel):
    id: str = Field(default_factory=_new_id)
    image: str
    status: JobStatus = JobStatus.QUEUED
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    scan: Optional[ScanResult] = None
    remediation: Optional[RemediationResult] = None
    signature: Optional[SignatureResult] = None
    alternatives: Optional[list[BaseAlternative]] = None
    alternatives_running: bool = False
    logs: list[LogEntry] = Field(default_factory=list)
    error: Optional[str] = None

    def touch(self) -> None:
        self.updated_at = _now()

    def log(self, message: str, level: Literal["info", "warn", "error"] = "info") -> None:
        self.logs.append(LogEntry(level=level, message=message))
        self.touch()


# ---- Request / response schemas ----------------------------------------------

class CreateScanRequest(BaseModel):
    image: str = Field(min_length=1, description="Registry image reference, e.g. nginx:1.25")
    auto_remediate: bool = False


class RemediateRequest(BaseModel):
    # copa: report-targeted patch · copa-all: comprehensive OS update · in-place: apt/apk/dnf upgrade
    strategy: Literal["copa", "copa-all", "in-place"] = "copa"


class SignRequest(BaseModel):
    key: str = "cosign.pub"


class ArtifactInfo(BaseModel):
    image: str = ""
    image_available: bool = False
    signature_available: bool = False
    pubkey_available: bool = False
    load_command: str = ""
    verify_command: str = ""


class PushRequest(BaseModel):
    target: str = Field(min_length=1, description="Destination ref, e.g. ghcr.io/me/app:1.0-secure")
    username: str = ""
    password: str = ""


class PushResult(BaseModel):
    target: str
    digest: str = ""
    signed: bool = False
    pull_command: str = ""
    verify_command: str = ""
    message: str = ""


class Suggestion(BaseModel):
    value: str
    kind: Literal["repo", "tag"] = "repo"
    official: bool = False
    description: str = ""
    stars: int = 0


class HealthResponse(BaseModel):
    status: str = "ok"
    demo_mode: bool = False
    tools: dict[str, bool] = Field(default_factory=dict)


class JobSummary(BaseModel):
    """Lightweight job view for list endpoints (omits vulnerability detail)."""

    id: str
    image: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    summary: Optional[ScanSummary] = None
    error: Optional[str] = None

    @classmethod
    def from_job(cls, job: Job) -> "JobSummary":
        return cls(
            id=job.id,
            image=job.image,
            status=job.status,
            created_at=job.created_at,
            updated_at=job.updated_at,
            summary=job.scan.summary if job.scan else None,
            error=job.error,
        )


T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    success: bool = True
    data: Optional[T] = None
    error: Optional[str] = None

    @classmethod
    def ok(cls, data: T) -> "Envelope[T]":
        return cls(success=True, data=data, error=None)

    @classmethod
    def fail(cls, error: str) -> "Envelope[T]":
        return cls(success=False, data=None, error=error)
