from __future__ import annotations

import asyncio
import os
import shlex
from pathlib import Path

from .config import CONFIG

MAX_OUTPUT = 3500


async def run_command(command: str, *, cwd: Path | None = None, timeout: int | None = None) -> str:
    timeout = timeout or CONFIG.shell_timeout
    env = os.environ.copy()
    env.setdefault("OPENCODE_TELEGRAM", "1")
    env.setdefault("TELEGRAM_BOT_TOKEN", CONFIG.bot_token)
    env.setdefault("TELEGRAM_CHAT_ID", str(CONFIG.allowed_user_id))
    env.setdefault("OPENCODE_URL", CONFIG.opencode_url)
    env.setdefault("OPENCODE_SERVER_PASSWORD", CONFIG.opencode_password)
    env.setdefault("OPENCODE_MODEL", CONFIG.model)
    env.setdefault("OPENCODE_BOT_DIR", str(CONFIG.install_dir))
    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(cwd) if cwd else None,
        env=env,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return f"[shell timed out after {timeout}s]"

    out = stdout.decode(errors="replace")
    err = stderr.decode(errors="replace")
    body = ""
    if out.strip():
        body += out.rstrip() + "\n"
    if err.strip():
        body += f"\n[stderr]\n{err.rstrip()}\n"
    body = body.strip()
    if len(body) > MAX_OUTPUT:
        body = body[:MAX_OUTPUT] + f"\n... [truncated, {len(body) - MAX_OUTPUT} more chars]"
    rc = f"\n[exit {proc.returncode}]"
    return (body or "(no output)") + rc
