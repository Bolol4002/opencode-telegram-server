#!/usr/bin/env python3
from __future__ import annotations

import os
import sys

import httpx


def main() -> int:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("notify: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID missing", file=sys.stderr)
        return 2

    if not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        text = " ".join(sys.argv[1:])
    text = (text or "").strip()
    if not text:
        return 0

    if len(text) > 4000:
        text = text[:3990] + "\n..."

    r = httpx.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={"chat_id": chat_id, "text": text, "disable_web_page_preview": "true"},
        timeout=30,
    )
    if r.status_code != 200 or not r.json().get("ok"):
        print(f"notify: telegram api error {r.status_code} {r.text}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
