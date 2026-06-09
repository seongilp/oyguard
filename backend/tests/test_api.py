import asyncio

import pytest

from app.models import JobStatus
from app.services.jobs import store


async def _wait_for(job_id: str, status: str, timeout: float = 5.0):
    elapsed = 0.0
    while elapsed < timeout:
        job = store.get(job_id)
        if job and job.status.value == status:
            return job
        await asyncio.sleep(0.05)
        elapsed += 0.05
    raise AssertionError(f"job {job_id} never reached {status} (now {store.get(job_id).status})")


async def test_health(client):
    res = await client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["data"]["demo_mode"] is True
    assert set(body["data"]["tools"]) == {"trivy", "grype", "cosign", "docker", "copa"}


async def test_create_scan_and_poll(client):
    res = await client.post("/api/scans", json={"image": "nginx:1.25"})
    assert res.status_code == 200
    job_id = res.json()["data"]["id"]

    job = await _wait_for(job_id, "scanned")
    assert job.scan is not None
    assert job.scan.summary.total > 0


async def test_full_pipeline(client):
    res = await client.post("/api/scans", json={"image": "nginx:1.25", "auto_remediate": True})
    job_id = res.json()["data"]["id"]

    job = await _wait_for(job_id, "signed")
    assert job.remediation is not None
    assert job.remediation.new_image.endswith("oy-remediated")
    assert job.remediation.remaining.critical == 0
    assert job.signature is not None
    assert job.signature.signed is True


async def test_manual_remediate_and_sign(client):
    res = await client.post("/api/scans", json={"image": "alpine:3.18"})
    job_id = res.json()["data"]["id"]
    await _wait_for(job_id, "scanned")

    res = await client.post(f"/api/scans/{job_id}/remediate", json={"strategy": "in-place"})
    assert res.status_code == 200
    await _wait_for(job_id, "remediated")

    res = await client.post(f"/api/scans/{job_id}/sign", json={"key": "cosign.pub"})
    assert res.status_code == 200
    await _wait_for(job_id, "signed")


async def test_remediate_before_scan_conflicts(client):
    job = await store.create("busybox:latest")
    res = await client.post(f"/api/scans/{job.id}/remediate", json={"strategy": "in-place"})
    assert res.status_code == 409


async def test_artifacts_after_remediation(client):
    res = await client.post("/api/scans", json={"image": "nginx:1.25", "auto_remediate": True})
    job_id = res.json()["data"]["id"]
    await _wait_for(job_id, "signed")

    res = await client.get(f"/api/scans/{job_id}/artifacts")
    assert res.status_code == 200
    info = res.json()["data"]
    assert info["image"].endswith("oy-remediated")
    assert info["image_available"] is True


async def test_artifacts_before_remediation_conflicts(client):
    res = await client.post("/api/scans", json={"image": "nginx:1.25"})
    job_id = res.json()["data"]["id"]
    await _wait_for(job_id, "scanned")
    res = await client.get(f"/api/scans/{job_id}/artifacts")
    assert res.status_code == 409


async def test_download_and_push_blocked_in_demo(client):
    res = await client.post("/api/scans", json={"image": "nginx:1.25", "auto_remediate": True})
    job_id = res.json()["data"]["id"]
    await _wait_for(job_id, "signed")

    res = await client.get(f"/api/scans/{job_id}/download/image")
    assert res.status_code == 409
    res = await client.post(f"/api/scans/{job_id}/push", json={"target": "localhost:5000/x:1"})
    assert res.status_code == 409


async def test_compare_bases(client):
    res = await client.post("/api/scans", json={"image": "nginx:1.25"})
    job_id = res.json()["data"]["id"]
    await _wait_for(job_id, "scanned")

    res = await client.post(f"/api/scans/{job_id}/compare")
    assert res.status_code == 200

    # poll until comparison done
    import asyncio as _a
    for _ in range(60):
        job = store.get(job_id)
        if job.alternatives is not None and not job.alternatives_running:
            break
        await _a.sleep(0.05)
    job = store.get(job_id)
    assert job.alternatives is not None
    images = [a.image for a in job.alternatives]
    assert any("alpine" in i for i in images)


async def test_strategy_validation(client):
    res = await client.post("/api/scans", json={"image": "nginx:1.25"})
    job_id = res.json()["data"]["id"]
    await _wait_for(job_id, "scanned")
    # invalid strategy rejected
    res = await client.post(f"/api/scans/{job_id}/remediate", json={"strategy": "bogus"})
    assert res.status_code == 422
    # copa-all accepted
    res = await client.post(f"/api/scans/{job_id}/remediate", json={"strategy": "copa-all"})
    assert res.status_code == 200


async def test_list_and_delete(client):
    res = await client.post("/api/scans", json={"image": "redis:7"})
    job_id = res.json()["data"]["id"]

    res = await client.get("/api/scans")
    assert any(j["id"] == job_id for j in res.json()["data"])

    res = await client.delete(f"/api/scans/{job_id}")
    assert res.json()["data"]["deleted"] is True

    res = await client.get(f"/api/scans/{job_id}")
    assert res.status_code == 404
