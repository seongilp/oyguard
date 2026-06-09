# oy-guard backend

FastAPI service that scans container images (Trivy + Grype), remediates them
(Wolfi rebase or in-place package upgrade), and signs the result with cosign.

## Requirements
- Python >= 3.12, [uv](https://docs.astral.sh/uv/)
- CLI tools on PATH for real runs: `trivy`, `grype`, `cosign`, `docker`

## Run
```bash
uv sync
uv run uvicorn app.main:app --reload --port 8000
```
API docs: http://localhost:8000/docs

### Demo mode (no images pulled, synthetic data so the UI works end-to-end)
```bash
OYGUARD_DEMO_MODE=true uv run uvicorn app.main:app --port 8000
```

## Test
```bash
uv run pytest -q
```

## Config (env vars, prefix `OYGUARD_`)
| Var | Default | Meaning |
|-----|---------|---------|
| `OYGUARD_DEMO_MODE` | `false` | Simulate tools instead of shelling out |
| `OYGUARD_WOLFI_BASE_IMAGE` | `cgr.dev/chainguard/wolfi-base:latest` | Rebase base |
| `OYGUARD_REMEDIATED_SUFFIX` | `oy-remediated` | New image tag suffix |
| `OYGUARD_COMMAND_TIMEOUT` | `600` | Per-tool timeout (s) |

See `../docs/API_CONTRACT.md` for the full API.
