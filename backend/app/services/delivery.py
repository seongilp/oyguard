"""Delivery of the remediated, signed image to the user.

Two ways to receive the result:

* **Download** — the remediated image as a ``docker load``-able tarball, plus the
  cosign signature bundle and public key for offline verification.
* **Push** — tag and push the image to a target registry, then sign it there so
  consumers can ``docker pull`` and ``cosign verify`` it.
"""
from __future__ import annotations

import os

from ..core import paths, shell
from ..core.config import get_settings
from ..models import ArtifactInfo, Job, PushResult


def _registry_host(target: str) -> str:
    """Best-effort registry host for ``docker login`` from an image reference."""
    first = target.split("/", 1)[0]
    if "." in first or ":" in first or first == "localhost":
        return first
    return "docker.io"


async def ensure_image_tar(job: Job) -> str:
    """Return a path to the remediated image tarball, creating it if needed.

    The signing step already exports the tar; this regenerates it on demand if
    it was cleaned up (or if signing was skipped).
    """
    if job.remediation is None:
        raise RuntimeError("조치된 이미지가 없습니다.")
    tar_path = paths.image_tar_path(job.id)
    if os.path.exists(tar_path):
        return tar_path
    os.makedirs(paths.artifact_dir(job.id), exist_ok=True)
    settings = get_settings()
    res = await shell.run(
        [settings.docker_bin, "save", "-o", tar_path, job.remediation.new_image],
        timeout=settings.command_timeout,
    )
    if not res.ok:
        raise RuntimeError(f"docker save failed: {res.stderr[-400:]}")
    return tar_path


def artifact_info(job: Job) -> ArtifactInfo:
    """Describe what can be downloaded for a job and how to use it."""
    image = job.remediation.new_image if job.remediation else ""
    has_tar = os.path.exists(paths.image_tar_path(job.id)) or job.remediation is not None
    has_bundle = os.path.exists(paths.bundle_path(job.id))
    has_pubkey = os.path.exists(paths.pubkey_path())

    load_cmd = f"docker load -i {os.path.basename(paths.image_tar_path(job.id))}"
    verify_cmd = (
        "cosign verify-blob --key cosign.pub "
        "--bundle image.bundle --insecure-ignore-tlog=true image.tar"
    )
    return ArtifactInfo(
        image=image,
        image_available=has_tar,
        signature_available=has_bundle,
        pubkey_available=has_pubkey,
        load_command=load_cmd,
        verify_command=verify_cmd if has_bundle else "",
    )


async def push_image(
    job: Job, target: str, username: str = "", password: str = ""
) -> PushResult:
    """Tag, push and (registry-)sign a job's remediated image at ``target``."""
    if job.remediation is None:
        raise RuntimeError("조치된 이미지가 없습니다.")
    return await push_ref(job.remediation.new_image, target, username, password)


async def push_ref(
    source: str, target: str, username: str = "", password: str = "", sign: bool = True
) -> PushResult:
    """Tag a local image, push it to ``target`` (by layer/digest — no tar), and
    optionally registry-sign it. Shared by the web API and the CLI; this is the
    scalable delivery path for large images (no docker save / tar download)."""
    settings = get_settings()

    if username and password:
        host = _registry_host(target)
        login = await shell.run(
            [settings.docker_bin, "login", host, "-u", username, "--password-stdin"],
            input_data=password,
            timeout=settings.command_timeout,
        )
        if not login.ok:
            raise RuntimeError(f"docker login 실패: {login.stderr[-300:]}")

    tag = await shell.run(
        [settings.docker_bin, "tag", source, target], timeout=120
    )
    if not tag.ok:
        raise RuntimeError(f"docker tag 실패: {tag.stderr[-300:]}")

    push = await shell.run(
        [settings.docker_bin, "push", target], timeout=settings.command_timeout
    )
    if not push.ok:
        raise RuntimeError(f"docker push 실패: {push.stderr[-400:]}")

    # Resolve the pushed digest for a stable, signable reference.
    digest = ""
    inspect = await shell.run(
        [settings.docker_bin, "image", "inspect", "--format", "{{json .RepoDigests}}", target],
        timeout=60,
    )
    if inspect.ok:
        import json

        try:
            repo = target.rsplit(":", 1)[0]
            for rd in json.loads(inspect.stdout or "[]"):
                if rd.startswith(repo + "@"):
                    digest = rd.split("@", 1)[1]
                    break
        except (json.JSONDecodeError, IndexError):
            digest = ""

    ref = f"{target.rsplit(':', 1)[0]}@{digest}" if digest else target

    # Sign the pushed image in the registry (offline key, no TUF/Rekor).
    signed = False
    sign_note = ""
    if sign:
        from . import signer

        await signer.ensure_keypair()
        env = {**os.environ, "COSIGN_PASSWORD": "", "COSIGN_YES": "true"}
        sign_res = await shell.run(
            [
                settings.cosign_bin,
                "sign",
                "--key",
                paths.key_path(),
                "--tlog-upload=false",
                "--use-signing-config=false",
                "--yes",
                ref,
            ],
            env=env,
            timeout=settings.command_timeout,
        )
        signed = sign_res.ok
        sign_note = "" if sign_res.ok else f" (서명 경고: {sign_res.stderr[-200:]})"

    return PushResult(
        target=target,
        digest=digest,
        signed=signed,
        pull_command=f"docker pull {ref}",
        verify_command=(
            f"cosign verify --key cosign.pub --insecure-ignore-tlog=true {ref}"
            if signed
            else ""
        ),
        message=f"{target} 푸시 완료{sign_note}",
    )
