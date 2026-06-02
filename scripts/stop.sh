#!/data/data/com.termux/files/usr/bin/bash
set -e

INSTALL_ROOT="/root/.opencode-telegram"
PIDFILE="$INSTALL_ROOT/bot.pid"
OC_PIDFILE="$INSTALL_ROOT/opencode.pid"

stop_pid() {
  local f="$1"
  local label="$2"
  if [ -f "$f" ]; then
    local pid
    pid=$(cat "$f" 2>/dev/null || true)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      sleep 1
      kill -9 "$pid" 2>/dev/null || true
      echo "[*] stopped $label (pid $pid)"
    fi
    rm -f "$f"
  fi
}

proot-distro login ubuntu --shared-tmp -- /bin/bash -c "
  pkill -f 'bot/main.py' 2>/dev/null || true
  pkill -f 'opencode serve' 2>/dev/null || true
  crontab -r 2>/dev/null || true
" || true

stop_pid "$PIDFILE" "bot"
stop_pid "$OC_PIDFILE" "opencode serve"

termux-wake-release 2>/dev/null || true
echo "[*] stopped."
