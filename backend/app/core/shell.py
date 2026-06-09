"""Thin async wrapper around subprocess for invoking external CLI tools."""
from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass


@dataclass
class CommandResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def tool_available(binary: str) -> bool:
    return shutil.which(binary) is not None


async def run(
    args: list[str],
    *,
    timeout: int = 600,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    input_data: str | None = None,
) -> CommandResult:
    """Run a command asynchronously and capture output.

    Raises asyncio.TimeoutError on timeout (process is killed first).
    """
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdin=asyncio.subprocess.PIPE if input_data is not None else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
        env=env,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input_data.encode() if input_data is not None else None),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise

    return CommandResult(
        returncode=proc.returncode if proc.returncode is not None else -1,
        stdout=stdout.decode(errors="replace"),
        stderr=stderr.decode(errors="replace"),
    )
