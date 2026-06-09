"""Hardened / minimal base image comparison.

Patching only fixes OS packages that have an available fix; the biggest lever
for "fix everything" is switching to a minimal or hardened base (alpine,
distroless, Chainguard/Wolfi). This service scans the original image alongside a
set of candidate equivalents and reports the vulnerability count of each, so the
user can see e.g. ``nginx:latest = 236`` vs ``nginx:alpine = 1`` and switch.
"""
from __future__ import annotations

import asyncio

from ..core import shell
from ..core.config import get_settings
from ..models import BaseAlternative, ScanSummary
from . import scanner


def _split(image: str) -> tuple[str, str]:
    ref = image.split("@", 1)[0]
    last = ref.rsplit("/", 1)[-1]
    if ":" in last:
        repo, tag = ref.rsplit(":", 1)
        return repo, tag
    return ref, "latest"


def candidate_images(image: str) -> list[str]:
    """Derive minimal/hardened candidate references for an image."""
    repo, tag = _split(image)
    short = repo.rsplit("/", 1)[-1]
    raw = [
        f"{repo}:alpine",
        f"{repo}:{tag}-alpine",
        f"{repo}:{tag}-slim",
        f"{repo}:{tag}-bookworm-slim",
        f"cgr.dev/chainguard/{short}:latest",
    ]
    original = f"{repo}:{tag}"
    out: list[str] = []
    for c in raw:
        if c != original and c != image and c not in out:
            out.append(c)
    return out[:5]


_NOTES = {
    "alpine": "Alpine 기반 — 작고 패키지가 적어 취약점이 적음",
    "slim": "Debian slim — 불필요한 패키지 제거",
    "chainguard": "Chainguard/Wolfi — near-zero CVE 하드닝 이미지 (인증 필요할 수 있음)",
}


def _note_for(image: str) -> str:
    for key, note in _NOTES.items():
        if key in image:
            return note
    return ""


async def _scan_summary(image: str) -> BaseAlternative:
    settings = get_settings()
    note = _note_for(image)
    if not shell.tool_available(settings.trivy_bin):
        return BaseAlternative(image=image, available=False, note=note, error="trivy 없음")
    res = await shell.run(
        [settings.trivy_bin, "image", "--quiet", "--format", "json", image],
        timeout=settings.command_timeout,
    )
    if not res.ok or not res.stdout.strip():
        err = res.stderr.strip().splitlines()[-1] if res.stderr.strip() else "이미지를 찾을 수 없음"
        return BaseAlternative(image=image, available=False, note=note, error=err[:160])
    vulns = scanner.parse_trivy(res.stdout)
    return BaseAlternative(
        image=image,
        available=True,
        summary=ScanSummary.from_vulns(vulns),
        note=note,
    )


def _demo_compare(image: str) -> list[BaseAlternative]:
    repo, tag = _split(image)
    original = BaseAlternative(
        image=image, available=True, note="현재 이미지",
        summary=ScanSummary(critical=2, high=12, medium=40, low=60, total=114),
    )
    alpine = BaseAlternative(
        image=f"{repo}:alpine", available=True, note=_NOTES["alpine"],
        summary=ScanSummary(critical=0, high=1, medium=0, low=0, total=1),
    )
    chainguard = BaseAlternative(
        image=f"cgr.dev/chainguard/{repo.rsplit('/', 1)[-1]}:latest",
        available=False, note=_NOTES["chainguard"], error="인증 필요 (demo)",
    )
    return [original, alpine, chainguard]


async def compare(image: str) -> list[BaseAlternative]:
    """Scan the original plus candidates concurrently; sort by total ascending.

    The original is always first marked with note "현재"; available candidates
    follow, sorted by vulnerability count; unavailable candidates go last.
    """
    if get_settings().demo_mode:
        return _demo_compare(image)
    candidates = candidate_images(image)
    sem = asyncio.Semaphore(min(get_settings().max_concurrency, 4))

    async def guarded(img: str) -> BaseAlternative:
        async with sem:
            return await _scan_summary(img)

    original_task = guarded(image)
    cand_tasks = [guarded(c) for c in candidates]
    original, *cands = await asyncio.gather(original_task, *cand_tasks)
    original.note = "현재 이미지"

    available = sorted(
        [c for c in cands if c.available], key=lambda c: c.summary.total
    )
    unavailable = [c for c in cands if not c.available]
    return [original, *available, *unavailable]
