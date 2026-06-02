# OpenCode Telegram Server

Run [OpenCode](https://opencode.ai) 24/7 on an always-on Android phone (Termux + Ubuntu proot), talk to it from anywhere in the world through Telegram, set cron jobs from the chat, and have it learn about you over time.

```
┌──────────────┐        ┌────────────────────────────┐
│  Telegram    │◀──────▶│  opencode serve  (127.0.0.1)│
│  (you, anywhere)        │   ▲                          │
└──────────────┘        │   │ opencode run --attach ... │
                        │   ▼                          │
                        │  Python bot (python-telegram-bot)│
                        │   ▲                          │
                        │   │ memory/, jobs.json, cron │
                        └────────────────────────────┘
```

- You: text the bot on Telegram.
- Bot: routes commands or calls opencode over its local HTTP server.
- opencode: replies using `opencode/minimax-m3-free` (or any model you set).
- Memory: each turn is journaled, facts get extracted into `MEMORY.md` and fed back in.
- Cron: you add jobs in plain English via `/cron add`; they run in `cron` and can ping you back.

## What you need

1. An Android phone that stays plugged in and on Wi-Fi (or with reliable mobile data).
2. [Termux](https://f-droid.org/packages/com.termux/) installed from F-Droid (the Play Store build is stale and broken).
3. [Termux:Boot](https://f-droid.org/packages/com.termux.boot/) so the server comes back after reboot.
4. A Telegram account.
5. ~1.5 GB free storage for Ubuntu proot + opencode.

## 1. Create the Telegram bot

1. Open Telegram, message [@BotFather](https://t.me/BotFather).
2. Send `/newbot`, follow the prompts, copy the **token** it gives you.
3. Message [@userinfobot](https://t.me/userinfobot) and copy the **numeric user ID** it replies with. This locks the server to you.

## 2. Install on the phone

Open Termux and run **one command**:

```bash
curl -fsSL https://raw.githubusercontent.com/Bolol4002/opencode-telegram-server/main/install.sh | bash
```

(Replace `Bolol4002` with your GitHub handle after you push this repo. While you're testing locally you can `git clone` this repo on the phone and run `./install.sh` from inside it.)

The script will:

1. Update Termux and install `proot-distro`, `git`, `python`, `openssl`.
2. Install Ubuntu inside proot.
3. Clone this repo into `~/.opencode-telegram-termux/repo` (Termux side) and `/root/.opencode-telegram/repo` (proot side).
4. Install Python dependencies into a venv at `/root/.opencode-telegram/venv`.
5. Launch the TUI installer (it runs inside the proot Ubuntu).

### The TUI installer asks for:

| Prompt | What to put |
|---|---|
| **Telegram bot token** | The token from BotFather. Validated live. |
| **Your numeric user ID** | From @userinfobot. Only this ID can use the bot. |
| **OpenCode model** | `provider/model` form. Default `opencode/minimax-m3-free`. |
| **Timezone** | IANA name, e.g. `Asia/Kolkata`. Affects cron firing times. |
| **OpenCode server password** | Auto-generated 40-char secret that blocks other apps on the phone from hitting the local opencode server. |

It then:

- Writes `/root/.opencode-telegram/.env` with all your settings.
- Writes `/root/.config/opencode/config.json` to pin your model.
- Starts the `cron` service inside proot.
- Verifies the bot token against Telegram.

After the TUI exits, `install.sh` drops a Termux:Boot hook at `~/.termux/boot/opencode-telegram.sh` so the server comes back after a reboot.

## 3. Start the server

Either reboot the phone (Termux:Boot will start everything), or in Termux:

```bash
bash ~/.opencode-telegram-termux/start.sh
```

To stop:

```bash
bash ~/.opencode-telegram-termux/stop.sh
```

To watch logs:

```bash
proot-distro login ubuntu -- tail -f /root/.opencode-telegram/logs/bot.out
proot-distro login ubuntu -- tail -f /root/.opencode-telegram/logs/opencode.log
```

## 4. Verify

Open Telegram, message your bot, send `/start`. You should see the welcome message.

Send anything else (e.g. `hi`) and the bot will reply using opencode.

## Commands reference

| Command | What it does |
|---|---|
| `/start` | Welcome / status |
| `/help` | Quick reference |
| `/status` | Model, opencode URL, paths, TZ |
| `/shell <cmd>` | Run a shell command in proot Ubuntu and return its output. **No sandbox.** |
| `@shell <cmd>` | Same as `/shell`, inline |
| `/cron add <text>` | Create a scheduled job from natural language. |
| `/cron list` | List all jobs |
| `/cron del <id>` | Delete a job |
| `/memory` | Show the long-term `MEMORY.md` index |
| `/forget` | Wipe the memory index and journal |
| `/restart` | Restart the bot process |
| anything else | Sent to opencode as a chat turn |

### Cron examples

```
/cron add every day at 9am, summarize top 5 stories from Hacker News and send them to me
/cron add every sunday 8pm, list open issues across my projects under /root/projects
/cron add every 30 minutes, curl -fsS https://example.com/healthz and alert me if it fails
```

The bot uses opencode to translate your text into a 5-field cron schedule + a bash command. The bash command is given the env vars `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `OPENCODE_URL`, `OPENCODE_SERVER_PASSWORD`, `OPENCODE_MODEL`, `OPENCODE_BOT_DIR` automatically, so cron jobs can:

- Send you a message:
  ```bash
  curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
    -d chat_id=$TELEGRAM_CHAT_ID --data-urlencode text="hello from cron"
  ```
- Run an opencode task and forward the result:
  ```bash
  opencode run --attach $OPENCODE_URL --model $OPENCODE_MODEL "summarize today's calendar" \
    | curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
        -d chat_id=$TELEGRAM_CHAT_ID --data-urlencode text="@-"
  ```
- Use the bundled notifier: `echo "msg" | python3 ~/.opencode-telegram/repo/bot/notify.py`

## How memory works

- Every chat turn is appended to `memory/journal/YYYY-MM-DD.md`.
- A second opencode call (background, after your reply) is asked to merge any new durable facts into `memory/MEMORY.md`. The index has three sections: **Identity**, **Preferences**, **Active projects**.
- On every new message, the index + the most recent journal are injected into the prompt as context.
- `/forget` wipes both. There is no per-fact deletion in v1 — edit `memory/MEMORY.md` by hand if you need surgical removal.

## Repo layout

```
.
├── install.sh              # Termux bootstrap + hands off to TUI
├── uninstall.sh            # Removes install, leaves proot intact
├── requirements.txt
├── .env.example            # Documented config template
├── tui/
│   └── installer.py        # Rich + questionary TUI
├── bot/
│   ├── main.py             # Telegram bot, command routing
│   ├── config.py           # Loads .env into a Config dataclass
│   ├── opencode_runner.py  # Wraps `opencode run --attach ...`
│   ├── memory.py           # Journal + MEMORY.md index
│   ├── cron_handler.py     # jobs.json + crontab sync
│   ├── shell.py            # /shell command execution
│   └── notify.py           # Helper for cron jobs to message you
└── scripts/
    ├── start.sh            # Starts opencode serve + bot + cron
    ├── stop.sh             # Stops everything
    └── boot.sh             # Termux:Boot entry point
```

After install there are two install roots on the phone:

- `~/.opencode-telegram-termux/` (in Termux) — the start/stop/boot scripts you run by hand.
- `/root/.opencode-telegram/` (inside proot Ubuntu) — the real config, repo checkout, venv, memory, logs.

## Configuration reference

All config lives in `~/.opencode-telegram/.env`. The TUI installer generates it; the bot reads it at startup. Most keys are self-explanatory; the interesting ones:

- `OPENCODE_MODEL` - `provider/model` string. Free defaults: `opencode/minimax-m3-free`. Paid: `anthropic/claude-sonnet-4-5`, `openai/gpt-5`, etc. See [opencode providers](https://opencode.ai/docs/providers).
- `OPENCODE_SERVER_PASSWORD` - any 32+ char random string. Blocks other apps on the phone from hitting the local server.
- `TZ` - IANA timezone. **Important:** cron inside proot Ubuntu reads this from the crontab preamble, so jobs fire on local time, not UTC.
- `SHELL_TIMEOUT` - max seconds for `/shell` commands. Default 120.

To switch models later, edit the file and `/restart`.

## Troubleshooting

**`opencode` not found.** Inside the proot, run `opencode auth login` first, or reinstall with `curl -fsSL https://opencode.ai/install | bash`. The model `opencode/minimax-m3-free` requires you to be logged in to the `opencode` provider.

**Bot never replies.** Check the log:
```
proot-distro login ubuntu -- tail -f /root/.opencode-telegram/logs/bot.out
```
Most often: wrong user ID in `.env`, or opencode server isn't running. From inside proot, `curl http://127.0.0.1:4096` should respond (it will 401 without the password, that's fine — it means the server is up).

**Cron job doesn't fire.** Inside proot, `service cron status` then `service cron start`. List jobs with `crontab -l | grep opencode-telegram-server`. Time zone is set in the crontab preamble, so double-check `TZ=...` in `/root/.opencode-telegram/.env`.

**Phone killed Termux in the background.** Re-open Termux once after a reboot, then close it. Termux:Boot will re-arm the autostart. If Android's battery optimization is aggressive, whitelist Termux in `Settings -> Apps -> Termux -> Battery -> Unrestricted`.

**Telegram says "bot was blocked" or "chat not found."** Send `/start` to your bot once in Telegram so the bot can register your chat; the TUI installer also uses the user ID you provide, so make sure they match.

## Security notes

- The bot is locked to a single Telegram user ID. Anyone else's messages are dropped silently.
- `OPENCODE_SERVER_PASSWORD` is required for any local HTTP call to opencode.
- `/shell` has no sandbox. The phone's storage is reachable. Don't expose the bot to anyone you don't trust with `rm -rf /`.
- The `.env` file contains your Telegram bot token. Don't commit it. It's in `.gitignore`.
- Cron jobs run as root inside proot. Same caveat.

## License

MIT.
