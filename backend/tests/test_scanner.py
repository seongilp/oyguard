from app.models import Severity
from app.services import scanner

TRIVY = """
{
  "Results": [
    {"Vulnerabilities": [
      {"VulnerabilityID": "CVE-1", "Severity": "CRITICAL", "PkgName": "curl",
       "InstalledVersion": "7.0", "FixedVersion": "8.0", "Title": "bad"},
      {"VulnerabilityID": "CVE-2", "Severity": "LOW", "PkgName": "tar",
       "InstalledVersion": "1.0", "FixedVersion": "", "Title": "minor"}
    ]}
  ]
}
"""

GRYPE = """
{
  "matches": [
    {"vulnerability": {"id": "CVE-1", "severity": "Critical",
      "fix": {"versions": ["8.0"]}, "description": "bad"},
     "artifact": {"name": "curl", "version": "7.0"}},
    {"vulnerability": {"id": "CVE-3", "severity": "High",
      "fix": {"versions": ["2.0"]}, "description": "other"},
     "artifact": {"name": "glibc", "version": "1.0"}}
  ]
}
"""


def test_parse_trivy():
    vulns = scanner.parse_trivy(TRIVY)
    assert len(vulns) == 2
    assert vulns[0].id == "CVE-1"
    assert vulns[0].severity is Severity.CRITICAL


def test_parse_grype():
    vulns = scanner.parse_grype(GRYPE)
    assert len(vulns) == 2
    assert vulns[0].fixed_version == "8.0"


def test_merge_dedupes_and_combines_sources():
    merged = scanner.merge(scanner.parse_trivy(TRIVY), scanner.parse_grype(GRYPE))
    by_id = {v.id: v for v in merged}
    # CVE-1 reported by both -> merged with both sources.
    assert set(by_id["CVE-1"].sources) == {"trivy", "grype"}
    # CVE-2 (trivy only) and CVE-3 (grype only) present.
    assert "CVE-2" in by_id and "CVE-3" in by_id
    # Sorted critical first.
    assert merged[0].severity is Severity.CRITICAL


def test_parse_handles_garbage():
    assert scanner.parse_trivy("not json") == []
    assert scanner.parse_grype("") == []


def test_normalize_image():
    from app.core.imageref import normalize_image

    assert normalize_image("nginx") == "nginx:latest"
    assert normalize_image("nginx:1.25") == "nginx:1.25"
    assert normalize_image("ghcr.io/org/app") == "ghcr.io/org/app:latest"
    assert normalize_image("localhost:5000/app") == "localhost:5000/app:latest"
    assert normalize_image("localhost:5000/app:1.0") == "localhost:5000/app:1.0"
    assert normalize_image("nginx@sha256:abc") == "nginx@sha256:abc"
