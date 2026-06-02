from __future__ import annotations

import asyncio
import logging
import os
import sys

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from . import cron_handler, memory, shell
from .config import CONFIG
from .opencode_runner import run

LOG_DIR = CONFIG.install_dir / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=getattr(logging, CONFIG.log_level, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "bot.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("bot")

if CONFIG.bot_token:
    os.environ.setdefault("TELEGRAM_BOT_TOKEN", CONFIG.bot_token)
if CONFIG.allowed_user_id:
    os.environ.setdefault("TELEGRAM_ALLOWED_USER_ID", str(CONFIG.allowed_user_id))


WELCOME = (
    "<b>OpenCode Telegram Server</b>\n\n"
    "Always-on AI agent on your phone. You talk, it talks back.\n\n"
    "Commands:\n"
    "  /start    - this message\n"
    "  /help     - command reference\n"
    "  /shell    - run a shell command (no sandbox)\n"
    "  /cron     - add / list / delete scheduled jobs\n"
    "  /memory   - show what the assistant remembers about you\n"
    "  /forget   - wipe memory index and journal\n"
    "  /status   - show runtime info\n"
    "  /restart  - restart the bot process\n\n"
    "Anything else gets sent to OpenCode as a chat message.\n"
    "Mention <code>@shell &lt;cmd&gt;</code> to run a command, or use /shell."
)


HELP = (
    "Commands:\n"
    "  /shell <cmd>     - run a shell command and return output\n"
    "  /cron add <text> - create a job from natural language\n"
    "  /cron list       - list current jobs\n"
    "  /cron del <id>   - delete job by id\n"
    "  /memory          - show MEMORY.md index\n"
    "  /forget          - wipe memory\n"
    "  /status          - show config, uptime, model\n"
    "  /restart         - restart the bot\n\n"
    "Cron examples:\n"
    "  /cron add every day at 9am, summarize Hacker News top stories\n"
    "  /cron add every sunday 8pm, list this week's open issues in /root/projects\n"
    "  /cron add every 30 minutes, ping https://example.com/health and alert me if down\n"
)


def _auth(update: Update) -> bool:
    uid = update.effective_user.id if update.effective_user else 0
    if uid != CONFIG.allowed_user_id:
        log.warning("Rejected update from user_id=%s", uid)
        return False
    return True


async def _typing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat:
        try:
            await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
        except Exception:
            pass


def _split_text(text: str, limit: int = 4000) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        cut = text.rfind("\n", 0, limit)
        if cut == -1:
            cut = limit
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return chunks


async def _reply(update: Update, text: str) -> None:
    if not update.effective_message:
        return
    for chunk in _split_text(text):
        await update.effective_message.reply_text(chunk, disable_web_page_preview=True)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _auth(update):
        return
    await update.effective_message.reply_text(WELCOME, parse_mode="HTML")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _auth(update):
        return
    await _reply(update, HELP)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _auth(update):
        return
    import shutil

    oc = shutil.which("opencode") or "not found"
    text = (
        f"model: {CONFIG.model}\n"
        f"opencode url: {CONFIG.opencode_url}\n"
        f"opencode binary: {oc}\n"
        f"install dir: {CONFIG.install_dir}\n"
        f"memory dir: {CONFIG.memory_dir}\n"
        f"tz: {CONFIG.tz}\n"
        f"shell timeout: {CONFIG.shell_timeout}s\n"
    )
    await _reply(update, text)


async def cmd_shell(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _auth(update):
        return
    cmd = " ".join(context.args or [])
    if not cmd:
        await _reply(update, "usage: /shell <command>")
        return
    await _typing(update, context)
    out = await shell.run_command(cmd)
    await _reply(update, f"$ {cmd}\n{out}")


async def cmd_memory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _auth(update):
        return
    index = memory.get_index() or "(empty)"
    await _reply(update, f"MEMORY.md:\n\n{index}")


async def cmd_forget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _auth(update):
        return
    memory.wipe()
    await _reply(update, "Memory wiped.")


async def cmd_restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _auth(update):
        return
    await _reply(update, "Restarting...")
    os.execv(sys.argv[0], sys.argv)


async def cmd_cron(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _auth(update):
        return
    args = context.args or []
    if not args:
        await _reply(
            update,
            "usage:\n  /cron add <natural language>\n  /cron list\n  /cron del <id>",
        )
        return
    sub = args[0].lower()
    if sub == "list":
        jobs = cron_handler.list_jobs()
        if not jobs:
            await _reply(update, "No cron jobs.")
            return
        lines = [f"#{j.id}  {j.schedule}  {j.command}" for j in jobs]
        await _reply(update, "Cron jobs:\n" + "\n".join(lines))
        return
    if sub == "del" and len(args) >= 2:
        try:
            jid = int(args[1])
        except ValueError:
            await _reply(update, "id must be a number")
            return
        ok = cron_handler.remove_job(jid)
        await _reply(update, f"Deleted #{jid}" if ok else f"No job with id {jid}")
        return
    if sub == "add":
        text = " ".join(args[1:]).strip()
        if not text:
            await _reply(update, "usage: /cron add <natural language>")
            return
        await _typing(update, context)
        try:
            job = await cron_handler.add_from_natural_language(text)
        except Exception as e:
            await _reply(update, f"Failed: {e}")
            return
        await _reply(
            update,
            f"Added job #{job.id}\nschedule: {job.schedule}\ncommand: {job.command}",
        )
        return
    await _reply(update, f"unknown subcommand: {sub}")


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _auth(update):
        return
    msg = update.effective_message
    if not msg or not msg.text:
        return
    text = msg.text.strip()

    if text.startswith("@shell "):
        cmd = text[len("@shell "):].strip()
        await _typing(update, context)
        out = await shell.run_command(cmd)
        await _reply(update, f"$ {cmd}\n{out}")
        return

    await _typing(update, context)
    context_prompt = memory.build_context(text)
    try:
        response = await run(context_prompt)
    except Exception as e:
        log.exception("opencode call failed")
        await _reply(update, f"[error talking to opencode] {e}")
        return
    await _reply(update, response)
    asyncio.create_task(_post_turn(text, response))


async def _post_turn(user_msg: str, assistant_msg: str) -> None:
    try:
        memory.append_journal(user_msg, assistant_msg)
    except Exception:
        log.exception("journal append failed")
    try:
        await memory.maybe_update_index(user_msg, assistant_msg)
    except Exception:
        log.exception("memory index update failed")


def build_app() -> Application:
    if not CONFIG.bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is empty. Run the TUI installer first.")
    app = Application.builder().token(CONFIG.bot_token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("shell", cmd_shell))
    app.add_handler(CommandHandler("memory", cmd_memory))
    app.add_handler(CommandHandler("forget", cmd_forget))
    app.add_handler(CommandHandler("restart", cmd_restart))
    app.add_handler(CommandHandler("cron", cmd_cron))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    return app


def main() -> None:
    log.info("starting bot, model=%s url=%s", CONFIG.model, CONFIG.opencode_url)
    app = build_app()
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
