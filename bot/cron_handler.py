from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass

from .config import CONFIG
from .opencode_runner import run

JOBS_FILE = CONFIG.data_dir / "jobs.json"
JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)

CRON_TAG = "# opencode-telegram-server"


@dataclass
class Job:
    id: int
    schedule: str
    command: str

    def to_cron_line(self) -> str:
        return f"{self.schedule} {self.command} {CRON_TAG}"


def _read_jobs() -> list[Job]:
    if not JOBS_FILE.exists():
        return []
    try:
        raw = json.loads(JOBS_FILE.read_text())
    except json.JSONDecodeError:
        return []
    return [Job(**j) for j in raw]


def _write_jobs(jobs: list[Job]) -> None:
    JOBS_FILE.write_text(json.dumps([asdict(j) for j in jobs], indent=2))


def _read_crontab() -> str:
    try:
        return subprocess.check_output(["crontab", "-l"], text=True)
    except subprocess.CalledProcessError:
        return ""


def _write_crontab(content: str) -> None:
    proc = subprocess.run(["crontab", "-"], input=content, text=True)
    proc.check_returncode()


def _sync_crontab(jobs: list[Job]) -> None:
    current = _read_crontab()
    lines = [ln for ln in current.splitlines() if CRON_TAG not in ln]
    lines = [ln for ln in lines if ln.strip()]
    for j in jobs:
        lines.append(j.to_cron_line())
    body = "\n".join(lines) + ("\n" if lines else "")
    body = (
        f"SHELL=/bin/bash\nPATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\n"
        f"OPENCODE_TELEGRAM=1\n"
        f"TELEGRAM_BOT_TOKEN={os.environ.get('TELEGRAM_BOT_TOKEN','')}\n"
        f"TELEGRAM_CHAT_ID={os.environ.get('TELEGRAM_ALLOWED_USER_ID','')}\n"
        f"OPENCODE_URL={CONFIG.opencode_url}\n"
        f"OPENCODE_SERVER_PASSWORD={CONFIG.opencode_password}\n"
        f"OPENCODE_MODEL={CONFIG.model}\n"
        f"OPENCODE_BOT_DIR={CONFIG.install_dir}\n"
        f"{body}"
    )
    _write_crontab(body)


def list_jobs() -> list[Job]:
    return _read_jobs()


def add_job(schedule: str, command: str) -> Job:
    schedule = schedule.strip()
    command = command.strip()
    if not re.match(r"^[\d\*\/\-\,]+(\s+[\d\*\/\-\,]+){4}$", schedule):
        raise ValueError(
            f"Invalid cron schedule: {schedule!r}. Expected 5 fields (m h dom mon dow)."
        )
    jobs = _read_jobs()
    next_id = (max((j.id for j in jobs), default=0)) + 1
    job = Job(id=next_id, schedule=schedule, command=command)
    jobs.append(job)
    _write_jobs(jobs)
    _sync_crontab(jobs)
    return job


def remove_job(job_id: int) -> bool:
    jobs = _read_jobs()
    kept = [j for j in jobs if j.id != job_id]
    if len(kept) == len(jobs):
        return False
    _write_jobs(kept)
    _sync_crontab(kept)
    return True


async def add_from_natural_language(text: str) -> Job:
    current = "\n".join(f"#{j.id} {j.schedule} {j.command}" for j in _read_jobs()) or "(none)"
    prompt = (
        "Convert the user's request into a single cron job for the user's phone.\n"
        "Return ONLY a JSON object: {\"schedule\": \"m h dom mon dow\", \"command\": \"...\"}.\n"
        "- The command runs in bash inside Ubuntu proot. It will have access to\n"
        "  $TELEGRAM_BOT_TOKEN, $TELEGRAM_CHAT_ID, $OPENCODE_URL,\n"
        "  $OPENCODE_SERVER_PASSWORD, $OPENCODE_MODEL, $OPENCODE_BOT_DIR.\n"
        "- To send the user a message, use:\n"
        "    curl -s -X POST \"https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage\" \\\n"
        "      -d chat_id=$TELEGRAM_CHAT_ID -d text=\"...\"\n"
        "- To ask opencode to do something and forward the result, use:\n"
        "    opencode run --attach $OPENCODE_URL --model $OPENCODE_MODEL \"<task>\" \\\n"
        "      | curl -s -X POST \"https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage\" \\\n"
        "          -d chat_id=$TELEGRAM_CHAT_ID --data-urlencode text=\"@-'\n"
        "- Pick a sensible schedule; if the user said 'every day at 9am' use '0 9 * * *'.\n"
        f"- Existing jobs (do not duplicate):\n{current}\n\n"
        f"User: {text}\n\n"
        "Return ONLY the JSON object."
    )
    raw = await run(prompt)
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        raise ValueError(f"Could not parse cron JSON from opencode: {raw!r}")
    data = json.loads(m.group(0))
    return add_job(data["schedule"], data["command"])
