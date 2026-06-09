"""HTTP API routes. All payloads are wrapped in the standard Envelope."""
from __future__ import annotations

import os

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse

from ..core import imageref, paths, shell
from ..core.config import get_settings
from ..models import (
    ArtifactInfo,
    CreateScanRequest,
    Envelope,
    HealthResponse,
    Job,
    JobStatus,
    JobSummary,
    PushRequest,
    PushResult,
    RemediateRequest,
    SignRequest,
    Suggestion,
)
from ..services import delivery, registry
from ..services.jobs import store

router = APIRouter(prefix="/api")


@router.get("/health", response_model=Envelope[HealthResponse])
async def health() -> Envelope[HealthResponse]:
    s = get_settings()
    tools = {
        "trivy": shell.tool_available(s.trivy_bin),
        "grype": shell.tool_available(s.grype_bin),
        "cosign": shell.tool_available(s.cosign_bin),
        "docker": shell.tool_available(s.docker_bin),
        "copa": shell.tool_available("copa"),
    }
    return Envelope.ok(HealthResponse(status="ok", demo_mode=s.demo_mode, tools=tools))


@router.get("/registry/suggest", response_model=Envelope[list[Suggestion]])
async def registry_suggest(q: str = "") -> Envelope[list[Suggestion]]:
    return Envelope.ok(await registry.suggest(q))


@router.post("/scans", response_model=Envelope[Job])
async def create_scan(req: CreateScanRequest, bg: BackgroundTasks) -> Envelope[Job]:
    job = await store.create(imageref.normalize_image(req.image))
    bg.add_task(store.run_scan, job.id, req.auto_remediate)
    return Envelope.ok(job)


@router.get("/scans", response_model=Envelope[list[JobSummary]])
async def list_scans() -> Envelope[list[JobSummary]]:
    return Envelope.ok([JobSummary.from_job(j) for j in store.list()])


@router.get("/scans/{job_id}", response_model=Envelope[Job])
async def get_scan(job_id: str) -> Envelope[Job]:
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return Envelope.ok(job)


@router.post("/scans/{job_id}/remediate", response_model=Envelope[Job])
async def remediate_scan(
    job_id: str, req: RemediateRequest, bg: BackgroundTasks
) -> Envelope[Job]:
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    if job.scan is None or job.status not in {JobStatus.SCANNED, JobStatus.REMEDIATED, JobStatus.FAILED}:
        raise HTTPException(status_code=409, detail=f"cannot remediate from status {job.status.value}")
    bg.add_task(store.run_remediate, job.id, req.strategy, False)
    return Envelope.ok(job)


@router.post("/scans/{job_id}/compare", response_model=Envelope[Job])
async def compare_bases(job_id: str, bg: BackgroundTasks) -> Envelope[Job]:
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    if not job.alternatives_running:
        bg.add_task(store.run_compare, job.id)
    return Envelope.ok(job)


@router.post("/scans/{job_id}/sign", response_model=Envelope[Job])
async def sign_scan(job_id: str, req: SignRequest, bg: BackgroundTasks) -> Envelope[Job]:
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    if job.remediation is None:
        raise HTTPException(status_code=409, detail="image must be remediated before signing")
    bg.add_task(store.run_sign, job.id, req.key)
    return Envelope.ok(job)


@router.delete("/scans/{job_id}", response_model=Envelope[dict])
async def delete_scan(job_id: str) -> Envelope[dict]:
    deleted = await store.delete(job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="job not found")
    return Envelope.ok({"deleted": True})


# ---- delivery: receive the remediated, signed image --------------------------

def _require_remediated(job_id: str) -> Job:
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    if job.remediation is None:
        raise HTTPException(status_code=409, detail="이미지가 아직 조치되지 않았습니다")
    return job


@router.get("/scans/{job_id}/artifacts", response_model=Envelope[ArtifactInfo])
async def get_artifacts(job_id: str) -> Envelope[ArtifactInfo]:
    job = _require_remediated(job_id)
    return Envelope.ok(delivery.artifact_info(job))


@router.get("/scans/{job_id}/download/image")
async def download_image(job_id: str):
    job = _require_remediated(job_id)
    if get_settings().demo_mode:
        raise HTTPException(status_code=409, detail="데모 모드에서는 실제 이미지가 없습니다")
    tar_path = await delivery.ensure_image_tar(job)
    safe = (job.remediation.new_image if job.remediation else "image").replace("/", "_").replace(":", "_")
    return FileResponse(tar_path, media_type="application/x-tar", filename=f"{safe}.tar")


@router.get("/scans/{job_id}/download/signature")
async def download_signature(job_id: str):
    _require_remediated(job_id)
    bundle = paths.bundle_path(job_id)
    if not os.path.exists(bundle):
        raise HTTPException(status_code=404, detail="서명 번들이 없습니다 (서명을 먼저 실행하세요)")
    return FileResponse(bundle, media_type="application/json", filename="image.bundle")


@router.get("/scans/{job_id}/download/pubkey")
async def download_pubkey(job_id: str):
    _require_remediated(job_id)
    pub = paths.pubkey_path()
    if not os.path.exists(pub):
        raise HTTPException(status_code=404, detail="공개키가 없습니다")
    return FileResponse(pub, media_type="application/x-pem-file", filename="cosign.pub")


@router.post("/scans/{job_id}/push", response_model=Envelope[PushResult])
async def push_image(job_id: str, req: PushRequest) -> Envelope[PushResult]:
    job = _require_remediated(job_id)
    if get_settings().demo_mode:
        raise HTTPException(status_code=409, detail="데모 모드에서는 푸시할 수 없습니다")
    try:
        result = await delivery.push_image(job, req.target.strip(), req.username, req.password)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc))
    job.log(result.message)
    store._save(job)
    return Envelope.ok(result)
