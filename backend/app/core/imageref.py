"""Image reference normalization.

Some tools (notably Copacetic) fail on a bare repository with no tag/digest
(``nginx`` -> "object required"), even though they warn about defaulting to
``latest``. Normalizing the reference once, at the system boundary, keeps the
whole pipeline (scan, patch, sign, tag) consistent.
"""
from __future__ import annotations


def normalize_image(image: str) -> str:
    """Append ``:latest`` when an image reference has no tag or digest.

    Handles registry host:port correctly (the ``:`` in ``localhost:5000/img``
    is a port, not a tag) by only inspecting the final path segment.
    """
    ref = image.strip()
    if not ref or "@" in ref:  # empty or has a digest
        return ref
    last_segment = ref.rsplit("/", 1)[-1]
    if ":" in last_segment:  # already tagged
        return ref
    return f"{ref}:latest"
