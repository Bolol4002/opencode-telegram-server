#!/data/data/com.termux/files/usr/bin/bash
set -e

proot-distro login ubuntu --shared-tmp -- /bin/bash -c '
LOG_DIR="/root/.opencode-telegram/logs"
INSTALL_ROOT="/root/.opencode-telegram"
mkdir -p "$LOG_DIR"
exec >> "$LOG_DIR/boot.log" 2>&1

echo "=== boot at $(date) ==="
service cron start 2>/dev/null || cron

set -a
. $INSTALL_ROOT/.env
set +a
export OPENCODE_SERVER_PASSWORD

if ! pgrep -f "opencode serve" >/dev/null; then
  setsid nohup opencode serve --hostname 127.0.0.1 --port 4096 \
    > $LOG_DIR/opencode.log 2>&1 < /dev/null &
  echo $! > $INSTALL_ROOT/opencode.pid
  disown
fi

if ! pgrep -f "bot/main.py" >/dev/null; then
  cd $INSTALL_ROOT/repo
  source $INSTALL_ROOT/venv/bin/activate
  export TELEGRAM_BOT_TOKEN TELEGRAM_ALLOWED_USER_ID
  setsid nohup python3 -m bot.main > $LOG_DIR/bot.out 2>&1 < /dev/null &
  echo $! > $INSTALL_ROOT/bot.pid
  disown
fi
'

termux-wake-lock 2>/dev/null || true
