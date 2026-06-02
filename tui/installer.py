from __future__ import annotations

import os
import secrets
import string
import subprocess
import sys
from pathlib import Path

import httpx
import questionary
from dotenv import dotenv_values, set_key
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt

console = Console()

REPO_DIR = Path(__file__).resolve().parent.parent
INSTALL_DIR = Path(os.environ.get("INSTALL_DIR", "/root/.opencode-telegram"))
ENV_PATH = INSTALL_DIR / ".env"
MEMORY_DIR = INSTALL_DIR / "memory"
DATA_DIR = INSTALL_DIR / "data"
LOG_DIR = INSTALL_DIR / "logs"
OPENCODE_CONFIG_DIR = Path("/root/.config/opencode")
OPENCODE_CONFIG_FILE = OPENCODE_CONFIG_DIR / "config.json"


def header(title: str) -> None:
    console.print()
    console.print(Panel.fit(f"[bold cyan]{title}[/bold cyan]", border_style="cyan"))


def step(msg: str) -> None:
    console.print(f"  [bold green]\\u2713[/bold green] {msg}")


def warn(msg: str) -> None:
    console.print(f"  [bold yellow]![/bold yellow] {msg}")


def fail(msg: str) -> None:
    console.print(f"  [bold red]x[/bold red] {msg}")
    sys.exit(1)


def random_password(length: int = 40) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def validate_token(token: str) -> bool:
    if ":" not in token or len(token) < 35:
        return False
    head, _ = token.split(":", 1)
    return head.isdigit()


async def test_bot_token(token: str) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"https://api.telegram.org/bot{token}/getMe")
            if r.status_code == 200 and r.json().get("ok"):
                return r.json()["result"]
    except Exception:
        return None
    return None


def detect_tz() -> str:
    try:
        out = subprocess.check_output(["timedatectl", "show", "-p", "Timezone", "--value"], text=True).strip()
        if out:
            return out
    except Exception:
        pass
    if os.path.exists("/etc/timezone"):
        return Path("/etc/timezone").read_text().strip()
    return "UTC"


def check_opencode() -> str | None:
    try:
        out = subprocess.check_output(["opencode", "--version"], text=True, stderr=subprocess.STDOUT)
        return out.strip()
    except Exception:
        return None


async def prompt_telegram_token() -> str:
    header("Step 1 / 6 - Telegram bot token")
    console.print(
        "  Open Telegram, message [bold]@BotFather[/bold], run [bold]/newbot[/bold],\n"
        "  and paste the token it gives you (looks like [green]123456789:AA...[/green])."
    )
    while True:
        token = Prompt.ask("  Bot token").strip()
        if not validate_token(token):
            warn("That doesn't look like a valid bot token. Try again.")
            continue
        with console.status("  Testing token against Telegram API..."):
            me = await test_bot_token(token)
        if not me:
            warn("Token rejected by Telegram. Double-check and try again.")
            continue
        step(f"Connected to bot: @{me.get('username')} ({me.get('first_name')})")
        return token


def prompt_user_id() -> int:
    header("Step 2 / 6 - Your Telegram user ID")
    console.print(
        "  Message [bold]@userinfobot[/bold] on Telegram; it will reply with your numeric ID.\n"
        "  Only messages from this ID will be accepted."
    )
    while True:
        raw = Prompt.ask("  Your numeric user ID")
        if raw.isdigit() and len(raw) >= 6:
            return int(raw)
        warn("That should be a number with 6+ digits.")


def prompt_model() -> str:
    header("Step 3 / 6 - OpenCode model")
    default = "opencode/minimax-m3-free"
    console.print(f"  Default: [green]{default}[/green]  (press Enter to accept)")
    m = Prompt.ask("  Model (provider/model)", default=default).strip()
    return m or default


def prompt_timezone() -> str:
    header("Step 4 / 6 - Timezone")
    detected = detect_tz()
    console.print(f"  Detected: [green]{detected}[/green]  (press Enter to accept)")
    tz = Prompt.ask("  Timezone (IANA, e.g. Asia/Kolkata)", default=detected).strip()
    return tz or "UTC"


def prompt_extras() -> dict:
    header("Step 5 / 6 - OpenCode server password")
    console.print(
        "  The bot calls OpenCode over a local HTTP server. A password blocks\n"
        "  anything else on the phone from poking at it. We'll auto-generate one."
    )
    pwd = random_password()
    step(f"Generated password ({len(pwd)} chars).")
    return {"OPENCODE_SERVER_PASSWORD": pwd}


def confirm_install() -> bool:
    header("Step 6 / 6 - Ready to install")
    console.print(f"  Install dir:  [green]{INSTALL_DIR}[/green]")
    console.print(f"  Repo dir:     [green]{REPO_DIR}[/green]")
    console.print(f"  Env file:     [green]{ENV_PATH}[/green]")
    return questionary.confirm("  Proceed?", default=True).ask()


def write_env(values: dict) -> None:
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    (MEMORY_DIR / "journal").mkdir(exist_ok=True)

    defaults = {
        "TELEGRAM_BOT_TOKEN": "",
        "TELEGRAM_ALLOWED_USER_ID": "",
        "OPENCODE_MODEL": "opencode/minimax-m3-free",
        "OPENCODE_HOST": "127.0.0.1",
        "OPENCODE_PORT": "4096",
        "INSTALL_DIR": str(INSTALL_DIR),
        "MEMORY_DIR": str(MEMORY_DIR),
        "DATA_DIR": str(DATA_DIR),
        "TZ": "UTC",
        "LOG_LEVEL": "INFO",
        "SHELL_TIMEOUT": "120",
    }
    defaults.update(values)

    if ENV_PATH.exists():
        existing = dotenv_values(ENV_PATH)
        for k, v in existing.items():
            defaults.setdefault(k, v)

    for k, v in defaults.items():
        set_key(str(ENV_PATH), k, str(v), quote_mode="never")
    step(f"Wrote {ENV_PATH}")


def write_opencode_config(model: str) -> None:
    OPENCODE_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    import json

    cfg = {"$schema": "https://opencode.ai/config.json", "model": model}
    OPENCODE_CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
    step(f"Wrote {OPENCODE_CONFIG_FILE}")


def setup_termux_boot() -> None:
    boot_dir = Path("/data/data/com.termux/files/home/.termux/boot")
    if not boot_dir.parent.exists():
        warn("Not running in Termux, skipping Termux:Boot setup.")
        return
    boot_dir.mkdir(parents=True, exist_ok=True)
    src = REPO_DIR / "scripts" / "boot.sh"
    dst = boot_dir / "opencode-telegram.sh"
    dst.write_text(src.read_text())
    dst.chmod(0o755)
    step(f"Installed Termux:Boot hook: {dst}")


def ensure_opencode() -> None:
    header("Checking OpenCode installation")
    v = check_opencode()
    if v:
        step(f"opencode found: {v}")
        return
    warn("opencode is not installed or not in PATH.")
    install = questionary.confirm("  Install opencode now via the official script?", default=True).ask()
    if not install:
        fail("OpenCode is required. Install it manually: curl -fsSL https://opencode.ai/install | bash")
    console.print("  Running installer (this can take a minute)...")
    rc = subprocess.call("bash -c 'curl -fsSL https://opencode.ai/install | bash'", shell=True)
    if rc != 0:
        fail("opencode install failed. Re-run this installer or install manually.")
    step("opencode installed.")


def ensure_cron() -> None:
    header("Checking cron daemon")
    rc = subprocess.call("service cron status >/dev/null 2>&1", shell=True)
    if rc == 0:
        step("cron is running.")
        return
    if not questionary.confirm("  cron is not running. Start it now?", default=True).ask():
        warn("Skipped. Cron jobs will not fire until you start cron.")
        return
    subprocess.call("service cron start", shell=True)
    step("cron started.")


def show_next_steps() -> None:
    header("All set.")
    console.print(
        Panel.fit(
            "[bold green]Installation complete.[/bold green]\n\n"
            f"Env file:      [cyan]{ENV_PATH}[/cyan]\n"
            f"Memory:        [cyan]{MEMORY_DIR}[/cyan]\n"
            f"Logs:          [cyan]{LOG_DIR}[/cyan]\n\n"
            "[bold]Start the bot now:[/bold]\n"
            "  [cyan]bash /root/.opencode-telegram/repo/scripts/start.sh[/cyan]\n\n"
            "[bold]Or just reboot the phone - Termux:Boot will start it for you.[/bold]\n\n"
            "Open Telegram, message your bot, send [green]/start[/green] to verify.",
            border_style="green",
        )
    )


async def main() -> None:
    console.print(
        Panel.fit(
            "[bold cyan]OpenCode Telegram Server[/bold cyan]\n"
            "TUI setup. You'll be asked a few questions,\n"
            "config and autostart will be written for you.",
            border_style="cyan",
        )
    )

    ensure_opencode()
    ensure_cron()

    token = await prompt_telegram_token()
    user_id = prompt_user_id()
    model = prompt_model()
    tz = prompt_timezone()
    extras = prompt_extras()

    if not confirm_install():
        console.print("[yellow]Aborted by user.[/yellow]")
        return

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as p:
        p.add_task("Writing configuration...", total=None)
        write_env(
            {
                "TELEGRAM_BOT_TOKEN": token,
                "TELEGRAM_ALLOWED_USER_ID": str(user_id),
                "OPENCODE_MODEL": model,
                "TZ": tz,
                **extras,
            }
        )
        write_opencode_config(model)
        setup_termux_boot()

    show_next_steps()


if __name__ == "__main__":
    import asyncio

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled.[/yellow]")
        sys.exit(130)
