"""Tests for remediation honesty: a failed re-scan must never be reported as
a successful "0 remaining" remediation."""
import os

import pytest

from app.core import paths
from app.models import ScanResult, ScanSummary, Severity, Vulnerability
from app.services import remediator, scanner


def _scan_with(total_critical: int = 2, total_high: int = 1) -> ScanResult:
    vulns = (
        [Vulnerability(id=f"CVE-C-{i}", severity=Severity.CRITICAL, package="p", fixed_version="2")
         for i in range(total_critical)]
        + [Vulnerability(id=f"CVE-H-{i}", severity=Severity.HIGH, package="q", fixed_version="2")
           for i in range(total_high)]
    )
    return ScanResult(summary=ScanSummary.from_vulns(vulns), vulnerabilities=vulns)


def test_build_result_honest_on_rescan_success():
    original = _scan_with(2, 1)  # total 3
    remaining = ScanSummary(critical=0, high=1, total=1)
    res = remediator._build_result(
        "img:patched", "img:1", "copa", original, remaining, rescan_ok=True, dockerfile="x"
    )
    assert res.rescan_ok is True
    assert res.remaining.total == 1
    assert res.fixed_count == 2  # 3 - 1


def test_build_result_does_not_fake_zero_on_rescan_failure():
    original = _scan_with(2, 1)  # total 3
    empty = ScanSummary()  # what a failed scan would produce
    res = remediator._build_result(
        "img:patched", "img:1", "copa", original, empty, rescan_ok=False, dockerfile="x"
    )
    # MUST NOT claim everything was fixed.
    assert res.rescan_ok is False
    assert res.fixed_count == 0
    # remaining falls back to the original counts, not a fabricated 0.
    assert res.remaining.total == original.summary.total == 3


async def test_rescan_summary_reports_failure(monkeypatch):
    async def boom(_image):
        raise RuntimeError("trivy exploded")

    monkeypatch.setattr(scanner, "scan_image", boom)
    summary, ok = await remediator._rescan_summary("img:patched")
    assert ok is False
    assert summary.total == 0  # empty, but the False flag prevents misuse


async def test_delete_removes_artifacts(client):
    from app.services.jobs import store

    res = await client.post("/api/scans", json={"image": "nginx:1.25"})
    job_id = res.json()["data"]["id"]
    # create a fake artifact dir for this job
    art = paths.artifact_dir(job_id)
    os.makedirs(art, exist_ok=True)
    with open(os.path.join(art, "image.tar"), "w") as fh:
        fh.write("dummy")
    assert os.path.isdir(art)

    res = await client.delete(f"/api/scans/{job_id}")
    assert res.status_code == 200
    assert not os.path.exists(art)
