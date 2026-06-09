"""Application configuration loaded from environment variables."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OYGUARD_", env_file=".env", extra="ignore")

    # CORS origins allowed to call the API (the Next.js frontend).
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:4000",
        "http://127.0.0.1:4000",
    ]

    # External tool binaries.
    trivy_bin: str = "trivy"
    grype_bin: str = "grype"
    cosign_bin: str = "cosign"
    docker_bin: str = "docker"

    # Suffix appended to remediated images, e.g. nginx:1.25 -> nginx:1.25-oy-remediated
    remediated_suffix: str = "oy-remediated"

    # Per-command timeout in seconds for external tools.
    command_timeout: int = 600

    # Working directory for build artifacts (Dockerfiles, cosign keys, etc.).
    work_dir: str = ".oyguard-work"

    # Max number of heavy pipeline operations (scan/build/sign) running at once.
    max_concurrency: int = 3

    # Optional outbound webhook (Slack/Discord/generic JSON) fired when a job
    # reaches a terminal state. Empty = disabled.
    webhook_url: str = ""

    # When true, scans/remediation are simulated instead of shelling out to real
    # tools. Useful for local UI development without pulling images. Auto-enabled
    # in tests.
    demo_mode: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
