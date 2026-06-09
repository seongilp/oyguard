"""Image signing with cosign.

A locally-built remediated image lives only in the Docker daemon, not in a
registry, so the usual ``cosign sign <registry-ref>`` flow (which signs by
digest and pushes the signature to the registry) does not apply. Instead we
sign **offline**:

1. ``docker save`` the image to a per-job tarball (also reused for download).
2. ``cosign sign-blob --use-signing-config=false --tlog-upload=false`` it with a
   local key pair.

Those two flags stop cosign from contacting the Sigstore transparency log
(Rekor) and the TUF repository, so signing works with no network, no
Fulcio/Rekor, and no dependence on ``~/.sigstore`` (which on some machines is
owned by root and not writable). The result is a detached signature bundle that
``cosign verify-blob --key cosign.pub`` can check.
"""
from __future__ import annotations

import os

from ..core import paths, shell
from ..core.config import get_settings
from ..models import SignatureResult


def _cosign_env() -> dict[str, str]:
    # Empty password for the generated key; never prompt; skip the transparency
    # log so no TUF/Rekor/Fulcio network calls are made.
    return {**os.environ, "COSIGN_PASSWORD": "", "COSIGN_YES": "true"}


async def ensure_keypair() -> tuple[str, str]:
    """Generate a cosign key pair under the work dir if one does not exist."""
    settings = get_settings()
    work = paths.keys_dir()
    key, pub = paths.key_path(), paths.pubkey_path()
    os.makedirs(work, exist_ok=True)
    if os.path.exists(key) and os.path.exists(pub):
        return key, pub

    res = await shell.run(
        [settings.cosign_bin, "generate-key-pair"],
        cwd=work,
        env=_cosign_env(),
        timeout=settings.command_timeout,
    )
    if not res.ok:
        raise RuntimeError(f"cosign generate-key-pair failed: {res.stderr[-500:]}")
    return key, pub


async def _docker_save(image: str, out_path: str) -> None:
    settings = get_settings()
    res = await shell.run(
        [settings.docker_bin, "save", "-o", out_path, image],
        timeout=settings.command_timeout,
    )
    if not res.ok:
        raise RuntimeError(f"docker save failed: {res.stderr[-500:]}")


async def _image_id(image: str) -> str:
    settings = get_settings()
    res = await shell.run(
        [settings.docker_bin, "image", "inspect", "--format", "{{.Id}}", image],
        timeout=60,
    )
    return res.stdout.strip() if res.ok else ""


async def sign_image(image: str, job_id: str, key_name: str = "cosign.pub") -> SignatureResult:
    settings = get_settings()

    if settings.demo_mode:
        return SignatureResult(
            signed=True,
            reference=f"{image}@sha256:" + "0" * 64,
            key=key_name,
            bundle="demo-signature-bundle",
        )

    key, pub = await ensure_keypair()
    env = _cosign_env()

    os.makedirs(paths.artifact_dir(job_id), exist_ok=True)
    tar_path = paths.image_tar_path(job_id)
    bundle_file = paths.bundle_path(job_id)

    # Export the locally-built image (tar is reused by the download endpoint),
    # then sign the tarball offline.
    await _docker_save(image, tar_path)
    image_id = await _image_id(image)

    res = await shell.run(
        [
            settings.cosign_bin,
            "sign-blob",
            "--key",
            key,
            "--use-signing-config=false",
            "--tlog-upload=false",
            "--yes",
            "--bundle",
            bundle_file,
            tar_path,
        ],
        env=env,
        timeout=settings.command_timeout,
    )
    if not res.ok:
        raise RuntimeError(f"cosign sign-blob failed: {res.stderr[-800:]}")

    signature = ""
    if os.path.exists(bundle_file):
        with open(bundle_file) as fh:
            signature = fh.read().strip()
    else:
        signature = res.stdout.strip()

    reference = f"{image}@{image_id}" if image_id else image
    return SignatureResult(
        signed=True,
        reference=reference,
        key=os.path.basename(pub),
        bundle=signature[:500],
    )
