from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from .config import CONFIG
from .opencode_runner import run

JOURNAL_DIR = CONFIG.memory_dir / "journal"
INDEX_FILE = CONFIG.memory_dir / "MEMORY.md"
MAX_INDEX_CHARS = 24_000
MAX_RECENT_CHARS = 6_000

JOURNAL_DIR.mkdir(parents=True, exist_ok=True)


def _today_path() -> Path:
    return JOURNAL_DIR / f"{date.today().isoformat()}.md"


def _read_text(path: Path, default: str = "") -> str:
    if path.exists():
        return path.read_text(encoding="replace")
    return default


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def get_index() -> str:
    return _read_text(INDEX_FILE)


def get_recent_journal(days: int = 2, char_limit: int = MAX_RECENT_CHARS) -> str:
    files = sorted(JOURNAL_DIR.glob("*.md"), reverse=True)[:days]
    chunks: list[str] = []
    total = 0
    for f in files:
        text = f.read_text(encoding="replace")
        if total + len(text) > char_limit:
            text = text[-(char_limit - total):]
        chunks.append(f"--- {f.name} ---\n{text}")
        total += len(text)
    return "\n\n".join(chunks)


def append_journal(user_msg: str, assistant_msg: str) -> None:
    path = _today_path()
    block = (
        f"\n\n## {date.today().isoformat()} turn\n"
        f"**user:** {user_msg.strip()[:4000]}\n\n"
        f"**assistant:** {assistant_msg.strip()[:4000]}\n"
    )
    with path.open("a", encoding="utf-8") as f:
        f.write(block)


async def maybe_update_index(user_msg: str, assistant_msg: str) -> None:
    current = get_index()
    prompt = (
        "You maintain a long-term MEMORY.md index about the user. Read the recent\n"
        "conversation and the current index, then return the full updated index.\n"
        "Rules:\n"
        "- Plain markdown, no frontmatter, no code fences.\n"
        "- Three sections: ## Identity, ## Preferences, ## Active projects.\n"
        "- Add only durable facts (name, job, location, recurring projects,\n"
        "  strong preferences, important people). Skip transient chatter.\n"
        "- Merge, don't duplicate. Drop stale or contradicted items.\n"
        "- Cap at 200 lines.\n\n"
        f"--- CURRENT MEMORY ---\n{current}\n--- END MEMORY ---\n\n"
        f"--- NEW TURN ---\nuser: {user_msg[:2000]}\nassistant: {assistant_msg[:2000]}\n--- END TURN ---\n\n"
        "Return ONLY the updated MEMORY.md contents, no commentary."
    )
    new = await run(prompt)
    new = _strip_fences(new)
    if new and len(new) < MAX_INDEX_CHARS:
        _write_text(INDEX_FILE, new)


def build_context(user_msg: str) -> str:
    index = get_index()
    recent = get_recent_journal()
    return (
        "You are a personal assistant running on the user's always-on Android phone.\n"
        "Answer concisely. The user is reaching you via Telegram; keep replies under\n"
        "4000 chars and avoid markdown tables larger than the chat width.\n\n"
        f"--- LONG-TERM MEMORY ---\n{index[:MAX_INDEX_CHARS]}\n--- END MEMORY ---\n\n"
        f"--- RECENT JOURNAL ---\n{recent}\n--- END RECENT ---\n\n"
        f"--- USER MESSAGE ---\n{user_msg}\n"
    )


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\n", "", text)
    text = re.sub(r"\n```$", "", text)
    return text.strip()


def export_all() -> dict:
    return {
        "memory_index": get_index(),
        "recent_journal": get_recent_journal(),
        "files": [p.name for p in sorted(JOURNAL_DIR.glob('*.md'))],
    }


def wipe() -> None:
    for p in [INDEX_FILE, *JOURNAL_DIR.glob("*.md")]:
        if p.exists():
            p.unlink()
