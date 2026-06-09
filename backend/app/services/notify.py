"""Outbound completion notifications.

When a job reaches a terminal state (``signed`` or ``failed``) and a webhook URL
is configured (``OYGUARD_WEBHOOK_URL``), POST a small JSON message. The payload
uses a ``text`` field, which Slack and Discord incoming webhooks both accept, so
the same URL works for either. Failures to notify are logged on the job but never
break the pipeline.
"""
from __future__ import annotations

import httpx

from ..core.config import get_settings
from ..models import Job, JobStatus


def _message(job: Job) -> str:
    if job.status is JobStatus.SIGNED:
        rem = job.remediation
        fixed = rem.fixed_count if rem else 0
        image = rem.new_image if rem else job.image
        return f"✅ oy-guard: {job.image} 조치 완료 — {image} ({fixed}건 해소, 서명됨)"
    return f"❌ oy-guard: {job.image} 실패 — {job.error or 'unknown error'}"


async def notify_terminal(job: Job) -> None:
    settings = get_settings()
    url = settings.webhook_url.strip()
    if not url:
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json={"text": _message(job)})
        job.log("완료 알림 전송됨")
    except Exception as exc:  # noqa: BLE001 - notification is best-effort
        job.log(f"완료 알림 전송 실패: {exc}", level="warn")
