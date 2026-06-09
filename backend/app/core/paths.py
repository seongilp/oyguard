"""Filesystem layout for per-job artifacts and signing keys.

Centralised so the signer (which produces artifacts) and the delivery service
(which serves them) agree on locations without importing each other.

Layout under ``work_dir``::

    keys/cosign.key, keys/cosign.pub        # shared signing key pair
    artifacts/<job_id>/image.tar            # docker save of remediated image
    artifacts/<job_id>/image.bundle         # cosign signature bundle
"""
from __future__ import annotations

import os

from .config import get_settings


def keys_dir() -> str:
    return os.path.join(get_settings().work_dir, "keys")


def key_path() -> str:
    return os.path.join(keys_dir(), "cosign.key")


def pubkey_path() -> str:
    return os.path.join(keys_dir(), "cosign.pub")


def artifact_dir(job_id: str) -> str:
    return os.path.join(get_settings().work_dir, "artifacts", job_id)


def image_tar_path(job_id: str) -> str:
    return os.path.join(artifact_dir(job_id), "image.tar")


def bundle_path(job_id: str) -> str:
    return os.path.join(artifact_dir(job_id), "image.bundle")
