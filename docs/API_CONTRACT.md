# oy-guard API Contract (v1)

Base URL: `http://localhost:8000` · Frontend: `http://localhost:4000`

> Single source of truth: this document is kept in sync with
> `backend/app/api/routes.py` and `backend/app/models.py`. If they disagree, the
> code wins — update this file.

All responses use the envelope:
```json
{ "success": true, "data": <payload>, "error": null }
```
On error (incl. 4xx/5xx HTTPException): `{ "success": false, "data": null, "error": "message" }`

## Job lifecycle (status)
`queued → scanning → scanned → remediating → remediated → signing → signed`
Any step may transition to terminal `failed` (with `error` set).
Terminal states: `signed`, `failed`.

## Models

### Vulnerability
```json
{
  "id": "CVE-2023-1234",
  "severity": "CRITICAL|HIGH|MEDIUM|LOW|UNKNOWN",
  "package": "openssl",
  "installed_version": "1.1.1",
  "fixed_version": "1.1.1n",     // "" when no fix is available
  "title": "short description",
  "sources": ["trivy", "grype"]
}
```

### ScanSummary
```json
{ "critical": 3, "high": 10, "medium": 5, "low": 2, "unknown": 0, "total": 20 }
```

### ScanResult
```json
{
  "summary": ScanSummary,
  "vulnerabilities": [Vulnerability],
  "trivy_summary": ScanSummary,
  "grype_summary": ScanSummary,
  "os_family": "debian"          // detected OS family, "" if unknown
}
```

### RemediationResult
```json
{
  "new_image": "nginx:1.25-oy-remediated",
  "base_image": "nginx:1.25",
  "strategy": "copa | copa-all | in-place",
  "remaining": ScanSummary,
  "fixed_count": 12,
  "dockerfile": "FROM ...",       // for copa: a comment with the copa command
  "rescan_ok": true               // false => re-scan failed; remaining=원본, fixed_count=0 (수치 미확인)
}
```
Strategies:
- `copa` — Copacetic patches only the vulnerabilities in a fresh Trivy report (default).
- `copa-all` — Copacetic comprehensive: upgrades every OS package.
- `in-place` — apt/apk/dnf upgrade on the original image (also the fallback if copa is missing/fails).

### SignatureResult
```json
{ "signed": true, "reference": "image@sha256:...", "key": "cosign.pub", "bundle": "..." }
```

### BaseAlternative (hardened-base comparison)
```json
{
  "image": "nginx:alpine",
  "available": true,             // false => couldn't scan (e.g. tag missing / auth)
  "summary": ScanSummary,
  "note": "Alpine 기반 …",
  "error": ""                    // populated when available=false
}
```

### Suggestion (Docker Hub autocomplete)
```json
{ "value": "nginx", "kind": "repo|tag", "official": true, "description": "...", "stars": 21287 }
```

### Job
```json
{
  "id": "uuid",
  "image": "nginx:1.25",          // normalized: bare repo gets :latest appended
  "status": "scanned",
  "created_at": "ISO8601",
  "updated_at": "ISO8601",
  "scan": ScanResult | null,
  "remediation": RemediationResult | null,
  "signature": SignatureResult | null,
  "alternatives": [BaseAlternative] | null,   // populated by /compare
  "alternatives_running": false,              // true while /compare runs
  "logs": [ { "ts": "ISO8601", "level": "info|warn|error", "message": "..." } ],
  "error": null
}
```
List endpoints return a lighter **JobSummary**: `id, image, status, created_at, updated_at, summary (ScanSummary|null), error`.

## Endpoints

| Method | Path | Body | Returns |
|--------|------|------|---------|
| GET  | `/api/health` | — | `{ "status": "ok", "demo_mode": false, "tools": { "trivy": true, "grype": true, "cosign": true, "docker": true, "copa": true } }` |
| GET  | `/api/registry/suggest?q=ngin` | — | `Suggestion[]` (Docker Hub proxy; repo or tag suggestions; best-effort, `[]` on error) |
| POST | `/api/scans` | `{ "image": "nginx:1.25", "auto_remediate": false }` | `Job` (status `queued`; scan runs in background) |
| GET  | `/api/scans` | — | `JobSummary[]` (newest first) |
| GET  | `/api/scans/{id}` | — | `Job` (full) · 404 if not found |
| POST | `/api/scans/{id}/remediate` | `{ "strategy": "copa" }` | `Job` · 409 unless status ∈ {scanned, remediated, failed} |
| POST | `/api/scans/{id}/compare` | — | `Job` (base comparison runs in background; poll `alternatives`) |
| POST | `/api/scans/{id}/sign` | `{ "key": "cosign.pub" }` | `Job` · 409 if not yet remediated |
| DELETE | `/api/scans/{id}` | — | `{ "deleted": true }` (also removes the job's artifacts) |
| GET  | `/api/scans/{id}/artifacts` | — | `ArtifactInfo` · 409 if not remediated |
| GET  | `/api/scans/{id}/download/image` | — | image `.tar` (`docker load`-able) · 409 in demo mode |
| GET  | `/api/scans/{id}/download/signature` | — | `image.bundle` · 404 if unsigned |
| GET  | `/api/scans/{id}/download/pubkey` | — | `cosign.pub` · 404 if missing |
| POST | `/api/scans/{id}/push` | `{ "target": "ghcr.io/me/app:1.0", "username": "", "password": "" }` | `PushResult` · 409 in demo mode · 502 on push failure |

### ArtifactInfo
```json
{
  "image": "nginx:1.25-oy-remediated",
  "image_available": true,
  "signature_available": true,
  "pubkey_available": true,
  "load_command": "docker load -i image.tar",
  "verify_command": "cosign verify-blob --key cosign.pub --bundle image.bundle --insecure-ignore-tlog=true image.tar"
}
```

### PushResult
```json
{
  "target": "ghcr.io/me/app:1.0",
  "digest": "sha256:...",
  "signed": true,
  "pull_command": "docker pull ghcr.io/me/app@sha256:...",
  "verify_command": "cosign verify --key cosign.pub --insecure-ignore-tlog=true ...",
  "message": "… 푸시 완료"
}
```

Processing runs in background tasks; clients poll `GET /api/scans/{id}`.

## CLI

The same services back a CLI for CI/registry-adjacent use (large images push by
digest — no tar). Run `./oyguard <cmd>` or `uv run python -m app.cli <cmd>`:

| Command | Purpose |
|---------|---------|
| `oyguard scan <image>` | Scan with Trivy + Grype, print severity summary |
| `oyguard fix <image> [--strategy copa\|copa-all\|in-place] [--push TARGET] [--no-sign]` | Scan → remediate; optionally push+sign |
| `oyguard push <image> <target> [--username --password] [--no-sign]` | Tag+push a local image to a registry, then sign |
| `oyguard sign <image> [--key cosign.pub]` | Offline blob-sign a local image |

## Frontend env
`NEXT_PUBLIC_API_BASE=http://localhost:8000`

## Backend env (prefix `OYGUARD_`)
`DEMO_MODE`, `WORK_DIR` (default `.oyguard-work`), `MAX_CONCURRENCY` (3), `COMMAND_TIMEOUT` (600s),
`REMEDIATED_SUFFIX` (`oy-remediated`), `WEBHOOK_URL` (Slack/Discord completion notify; empty = off),
`CORS_ORIGINS` (defaults allow localhost 3000 & 4000).
