"""Job store and async orchestration of the scan→remediate→sign pipeline.

Jobs run server-side in the background (independent of the HTTP request that
started them), are persisted to one JSON file each so they survive a backend
restart, and are capped to ``max_concurrency`` heavy operations at a time via a
shared semaphore. No external broker (Celery/Redis) is required: a single-node
tool whose workers must run where Docker/Trivy/Grype/cosign live gains nothing
from a distributed queue.
"""
from __future__ import annotations

import asyncio
import os
import shutil

from ..core import paths
from ..core.config import get_settings
from ..models import Job, JobStatus
from . import alternatives, notify, remediator, scanner, signer

# Cap concurrent heavy work (image pulls, scans, builds, signing).
_sema = asyncio.Semaphore(get_settings().max_concurrency)


def _jobs_dir() -> str:
    return os.path.join(get_settings().work_dir, "jobs")


class JobStore:
    """In-memory cache backed by per-job JSON files on disk."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = asyncio.Lock()

    # ---- persistence ---------------------------------------------------------

    def _path(self, job_id: str) -> str:
        return os.path.join(_jobs_dir(), f"{job_id}.json")

    def _save(self, job: Job) -> None:
        os.makedirs(_jobs_dir(), exist_ok=True)
        tmp = self._path(job.id) + ".tmp"
        with open(tmp, "w") as fh:
            fh.write(job.model_dump_json())
        os.replace(tmp, self._path(job.id))  # atomic

    def load_all(self) -> None:
        """Load persisted jobs on startup; mark interrupted ones as failed."""
        directory = _jobs_dir()
        if not os.path.isdir(directory):
            return
        for name in os.listdir(directory):
            if not name.endswith(".json"):
                continue
            try:
                with open(os.path.join(directory, name)) as fh:
                    job = Job.model_validate_json(fh.read())
            except Exception:  # noqa: BLE001 - skip corrupt files
                continue
            if job.status not in {JobStatus.SIGNED, JobStatus.FAILED, JobStatus.SCANNED, JobStatus.REMEDIATED, JobStatus.QUEUED}:
                # Was mid-flight when the process stopped — cannot resume safely.
                job.status = JobStatus.FAILED
                job.error = "백엔드 재시작으로 중단되었습니다. 다시 시도하세요."
                job.log(job.error, level="warn")
                self._save(job)
            self._jobs[job.id] = job

    # ---- CRUD ----------------------------------------------------------------

    async def create(self, image: str) -> Job:
        job = Job(image=image)
        job.log(f"이미지 등록: {image}")
        async with self._lock:
            self._jobs[job.id] = job
            self._save(job)
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)

    async def delete(self, job_id: str) -> bool:
        async with self._lock:
            job = self._jobs.pop(job_id, None)
        if job is None:
            return False
        try:
            os.remove(self._path(job_id))
        except FileNotFoundError:
            pass
        # Also remove the job's artifacts (image tar, signature bundle) so the
        # work dir doesn't grow unbounded — these are often hundreds of MB.
        shutil.rmtree(paths.artifact_dir(job_id), ignore_errors=True)
        return True

    # ---- pipeline steps ------------------------------------------------------

    async def run_scan(self, job_id: str, auto_remediate: bool = False) -> None:
        job = self.get(job_id)
        if job is None:
            return
        try:
            job.status = JobStatus.SCANNING
            job.log("Trivy · Grype 스캔 시작")
            self._save(job)
            async with _sema:
                job.scan = await scanner.scan_image(job.image)
            job.status = JobStatus.SCANNED
            s = job.scan.summary
            job.log(
                f"스캔 완료 — 총 {s.total}건 (Critical {s.critical}, High {s.high}, "
                f"Medium {s.medium}, Low {s.low})"
            )
            self._save(job)
        except Exception as exc:  # noqa: BLE001
            await self._fail(job, f"스캔 실패: {exc}")
            return

        if auto_remediate:
            await self.run_remediate(job_id, strategy="copa", auto_sign=True)

    async def run_remediate(
        self, job_id: str, strategy: str = "copa", auto_sign: bool = False
    ) -> None:
        job = self.get(job_id)
        if job is None or job.scan is None:
            return
        try:
            job.status = JobStatus.REMEDIATING
            job.log(f"조치 시작 — 전략: {strategy}")
            self._save(job)
            async with _sema:
                job.remediation = await remediator.remediate(job.image, job.scan, strategy)
            job.status = JobStatus.REMEDIATED
            r = job.remediation
            job.log(
                f"조치 완료 — 새 이미지 {r.new_image} (베이스 {r.base_image}), "
                f"{r.fixed_count}건 해소, 잔여 {r.remaining.total}건"
            )
            self._save(job)
        except Exception as exc:  # noqa: BLE001
            await self._fail(job, f"조치 실패: {exc}")
            return

        if auto_sign:
            await self.run_sign(job_id)

    async def run_sign(self, job_id: str, key: str = "cosign.pub") -> None:
        job = self.get(job_id)
        if job is None or job.remediation is None:
            return
        try:
            job.status = JobStatus.SIGNING
            job.log("cosign 서명 시작")
            self._save(job)
            async with _sema:
                job.signature = await signer.sign_image(job.remediation.new_image, job.id, key)
            job.status = JobStatus.SIGNED
            job.log(f"서명 완료 — {job.signature.reference}")
            self._save(job)
            await notify.notify_terminal(job)
            self._save(job)
        except Exception as exc:  # noqa: BLE001
            await self._fail(job, f"서명 실패: {exc}")

    async def run_compare(self, job_id: str) -> None:
        """Scan minimal/hardened base alternatives (independent of the pipeline)."""
        job = self.get(job_id)
        if job is None:
            return
        job.alternatives_running = True
        job.log("하드닝 베이스 비교 시작")
        self._save(job)
        try:
            async with _sema:
                job.alternatives = await alternatives.compare(job.image)
            best = min(
                (a for a in job.alternatives if a.available),
                key=lambda a: a.summary.total,
                default=None,
            )
            if best and best.image != job.image:
                job.log(f"베이스 비교 완료 — 최소 취약점: {best.image} ({best.summary.total}건)")
            else:
                job.log("베이스 비교 완료")
        except Exception as exc:  # noqa: BLE001
            job.log(f"베이스 비교 실패: {exc}", level="warn")
        finally:
            job.alternatives_running = False
            self._save(job)

    async def _fail(self, job: Job, message: str) -> None:
        job.status = JobStatus.FAILED
        job.error = message
        job.log(message, level="error")
        self._save(job)
        await notify.notify_terminal(job)
        self._save(job)


store = JobStore()
