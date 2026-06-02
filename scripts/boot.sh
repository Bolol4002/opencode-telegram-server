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

if ! pgrep -f "opencode serve" >/dev/null && ! pgrep -f "bot.main" >/dev/null; then
  if ! pgrep -f "proot-supervisor.sh start" >/dev/null; then
    setsid /root/.opencode-telegram/repo/scripts/proot-supervisor.sh start \
      > /root/.opencode-telegram/logs/supervisor.out 2>&1 < /dev/null &
    disown
  fi
fi
'

termux-wake-lock 2>/dev/null || true
