"""Image reference autocomplete backed by the Docker Hub API.

Proxied through the backend so the browser never hits Docker Hub directly
(avoids CORS and keeps it cacheable/rate-limitable server-side).

* ``nginx``        -> repository suggestions (official + community)
* ``nginx:1.2``    -> tag suggestions for that repository
"""
from __future__ import annotations

import httpx

from ..models import Suggestion

_SEARCH_URL = "https://hub.docker.com/v2/search/repositories/"
_TAGS_URL = "https://hub.docker.com/v2/repositories/{ns}/{name}/tags/"


def _split_repo(repo: str) -> tuple[str, str]:
    """Return (namespace, name); official images live under ``library``."""
    if "/" in repo:
        ns, name = repo.split("/", 1)
        return ns, name
    return "library", repo


async def suggest(query: str, limit: int = 8) -> list[Suggestion]:
    q = query.strip()
    if not q:
        return []
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            if ":" in q:
                return await _suggest_tags(client, q, limit)
            return await _suggest_repos(client, q, limit)
    except Exception:  # noqa: BLE001 - autocomplete is best-effort
        return []


async def _suggest_repos(
    client: httpx.AsyncClient, q: str, limit: int
) -> list[Suggestion]:
    res = await client.get(_SEARCH_URL, params={"query": q, "page_size": limit})
    res.raise_for_status()
    out: list[Suggestion] = []
    for r in res.json().get("results", [])[:limit]:
        name = r.get("repo_name", "")
        if not name:
            continue
        out.append(
            Suggestion(
                value=name,
                kind="repo",
                official=bool(r.get("is_official")),
                description=(r.get("short_description") or "")[:80],
                stars=int(r.get("star_count") or 0),
            )
        )
    return out


async def _suggest_tags(
    client: httpx.AsyncClient, q: str, limit: int
) -> list[Suggestion]:
    repo, _, tag_prefix = q.rpartition(":")
    ns, name = _split_repo(repo)
    res = await client.get(
        _TAGS_URL.format(ns=ns, name=name),
        params={"page_size": 50, "ordering": "last_updated", "name": tag_prefix},
    )
    res.raise_for_status()
    out: list[Suggestion] = []
    for t in res.json().get("results", []):
        tag = t.get("name", "")
        if not tag or (tag_prefix and not tag.startswith(tag_prefix)):
            continue
        out.append(Suggestion(value=f"{repo}:{tag}", kind="tag", official=False))
        if len(out) >= limit:
            break
    return out
