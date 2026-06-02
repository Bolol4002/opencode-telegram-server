from __future__ import annotations

import asyncio
import os
from typing import AsyncIterator

from .config import CONFIG


async def _read_stream(stream: asyncio.StreamReader) -> AsyncIterator[str]:
    while True:
        line = await stream.readline()
        if not line:
            return
        yield line.decode(errors="replace").rstrip()


async def run(prompt: str, *, session: str | None = None, model: str | None = None) -> str:
    cmd = [
        "opencode",
        "run",
        "--attach",
        CONFIG.opencode_url,
        "--model",
        model or CONFIG.model,
    ]
    if session:
        cmd += ["--session", session]
    env = os.environ.copy()
    if CONFIG.opencode_password:
        env["OPENCODE_SERVER_PASSWORD"] = CONFIG.opencode_password
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=prompt.encode()), timeout=600
        )
    except asyncio.TimeoutError:
        proc.kill()
        return "[opencode timed out after 10 minutes]"
    if proc.returncode != 0:
        err = stderr.decode(errors="replace").strip()
        return f"[opencode error {proc.returncode}] {err or 'no stderr'}"
    return stdout.decode(errors="replace").strip()


async def run_stream(prompt: str, *, model: str | None = None) -> AsyncIterator[str]:
    cmd = [
        "opencode",
        "run",
        "--attach",
        CONFIG.opencode_url,
        "--format",
        "json",
        "--model",
        model or CONFIG.model,
    ]
    env = os.environ.copy()
    if CONFIG.opencode_password:
        env["OPENCODE_SERVER_PASSWORD"] = CONFIG.opencode_password
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    assert proc.stdin is not None
    proc.stdin.write(prompt.encode())
    proc.stdin.close()
    assert proc.stdout is not None
    async for line in _read_stream(proc.stdout):
        yield line
    await proc.wait()
