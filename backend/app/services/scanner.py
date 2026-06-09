"""Vulnerability scanning via Trivy and Grype.

Both scanners run against the same image reference; their findings are parsed
into the common ``Vulnerability`` model and merged (deduplicated by
CVE id + package), recording which scanners reported each finding.
"""
from __future__ import annotations

import json

from ..core import shell
from ..core.config import get_settings
from ..models import ScanResult, ScanSummary, Severity, Vulnerability

_SEVERITY_MAP = {
    "CRITICAL": Severity.CRITICAL,
    "HIGH": Severity.HIGH,
    "MEDIUM": Severity.MEDIUM,
    "LOW": Severity.LOW,
    "NEGLIGIBLE": Severity.LOW,
    "UNKNOWN": Severity.UNKNOWN,
}


def _sev(raw: str | None) -> Severity:
    return _SEVERITY_MAP.get((raw or "").upper(), Severity.UNKNOWN)


def parse_trivy(stdout: str) -> list[Vulnerability]:
    """Parse `trivy image -f json` output."""
    vulns: list[Vulnerability] = []
    try:
        data = json.loads(stdout or "{}")
    except json.JSONDecodeError:
        return vulns
    for result in data.get("Results", []) or []:
        for v in result.get("Vulnerabilities", []) or []:
            vulns.append(
                Vulnerability(
                    id=v.get("VulnerabilityID", "UNKNOWN"),
                    severity=_sev(v.get("Severity")),
                    package=v.get("PkgName", ""),
                    installed_version=v.get("InstalledVersion", ""),
                    fixed_version=v.get("FixedVersion", ""),
                    title=v.get("Title") or v.get("Description", "")[:200],
                    sources=["trivy"],
                )
            )
    return vulns


def parse_trivy_os(stdout: str) -> str:
    """Extract the OS family (debian/ubuntu/alpine/rhel/...) from trivy output."""
    try:
        data = json.loads(stdout or "{}")
    except json.JSONDecodeError:
        return ""
    return (data.get("Metadata", {}).get("OS", {}) or {}).get("Family", "") or ""


def parse_grype_os(stdout: str) -> str:
    try:
        data = json.loads(stdout or "{}")
    except json.JSONDecodeError:
        return ""
    return (data.get("distro", {}) or {}).get("name", "") or ""


def parse_grype(stdout: str) -> list[Vulnerability]:
    """Parse `grype -o json` output."""
    vulns: list[Vulnerability] = []
    try:
        data = json.loads(stdout or "{}")
    except json.JSONDecodeError:
        return vulns
    for match in data.get("matches", []) or []:
        vuln = match.get("vulnerability", {}) or {}
        artifact = match.get("artifact", {}) or {}
        fixed = ""
        fix = vuln.get("fix", {}) or {}
        versions = fix.get("versions") or []
        if versions:
            fixed = versions[0]
        vulns.append(
            Vulnerability(
                id=vuln.get("id", "UNKNOWN"),
                severity=_sev(vuln.get("severity")),
                package=artifact.get("name", ""),
                installed_version=artifact.get("version", ""),
                fixed_version=fixed,
                title=(vuln.get("description") or "")[:200],
                sources=["grype"],
            )
        )
    return vulns


def merge(trivy: list[Vulnerability], grype: list[Vulnerability]) -> list[Vulnerability]:
    """Merge findings, deduplicating by (cve id, package)."""
    merged: dict[tuple[str, str], Vulnerability] = {}
    for v in trivy + grype:
        key = (v.id, v.package)
        if key in merged:
            existing = merged[key]
            for src in v.sources:
                if src not in existing.sources:
                    existing.sources.append(src)
            # Prefer a concrete fixed version if we have one.
            if not existing.fixed_version and v.fixed_version:
                existing.fixed_version = v.fixed_version
        else:
            merged[key] = v.model_copy(deep=True)
    # Sort by severity weight (critical first) then id.
    order = {
        Severity.CRITICAL: 0,
        Severity.HIGH: 1,
        Severity.MEDIUM: 2,
        Severity.LOW: 3,
        Severity.UNKNOWN: 4,
    }
    return sorted(merged.values(), key=lambda v: (order[v.severity], v.id))


async def scan_image(image: str) -> ScanResult:
    """Run both scanners and return a merged ScanResult.

    In demo mode (or when binaries are missing) returns synthetic data so the
    full UI flow works without pulling images.
    """
    settings = get_settings()
    if settings.demo_mode:
        return _demo_scan(image)

    trivy_vulns: list[Vulnerability] = []
    grype_vulns: list[Vulnerability] = []
    os_family = ""

    if shell.tool_available(settings.trivy_bin):
        res = await shell.run(
            [settings.trivy_bin, "image", "--quiet", "--format", "json", image],
            timeout=settings.command_timeout,
        )
        if res.ok or res.stdout.strip():
            trivy_vulns = parse_trivy(res.stdout)
            os_family = parse_trivy_os(res.stdout) or os_family

    if shell.tool_available(settings.grype_bin):
        res = await shell.run(
            [settings.grype_bin, image, "-o", "json"],
            timeout=settings.command_timeout,
        )
        if res.ok or res.stdout.strip():
            grype_vulns = parse_grype(res.stdout)
            os_family = os_family or parse_grype_os(res.stdout)

    merged = merge(trivy_vulns, grype_vulns)
    return ScanResult(
        summary=ScanSummary.from_vulns(merged),
        vulnerabilities=merged,
        trivy_summary=ScanSummary.from_vulns(trivy_vulns),
        grype_summary=ScanSummary.from_vulns(grype_vulns),
        os_family=os_family,
    )


def _demo_scan(image: str) -> ScanResult:
    sample = [
        Vulnerability(id="CVE-2023-38545", severity=Severity.CRITICAL, package="curl",
                      installed_version="7.88.1", fixed_version="8.4.0",
                      title="curl SOCKS5 heap buffer overflow", sources=["trivy", "grype"]),
        Vulnerability(id="CVE-2023-4911", severity=Severity.HIGH, package="glibc",
                      installed_version="2.36", fixed_version="2.37",
                      title="glibc ld.so buffer overflow (Looney Tunables)", sources=["trivy", "grype"]),
        Vulnerability(id="CVE-2023-5678", severity=Severity.MEDIUM, package="openssl",
                      installed_version="3.0.9", fixed_version="3.0.12",
                      title="OpenSSL DH key generation DoS", sources=["grype"]),
        Vulnerability(id="CVE-2022-48303", severity=Severity.LOW, package="tar",
                      installed_version="1.34", fixed_version="1.35",
                      title="tar one-byte out-of-bounds read", sources=["trivy"]),
    ]
    return ScanResult(
        summary=ScanSummary.from_vulns(sample),
        vulnerabilities=sample,
        trivy_summary=ScanSummary.from_vulns([v for v in sample if "trivy" in v.sources]),
        grype_summary=ScanSummary.from_vulns([v for v in sample if "grype" in v.sources]),
        os_family="debian",
    )
