#!/bin/bash
set -e

INSTALL_ROOT="/root/.opencode-telegram"
REPO_DIR="$INSTALL_ROOT/repo"
VENV="$INSTALL_ROOT/venv"
LOG_DIR="$INSTALL_ROOT/logs"
OC_PIDFILE="$INSTALL_ROOT/opencode.pid"
BOT_PIDFILE="$INSTALL_ROOT/bot.pid"
mkdir -p "$LOG_DIR"

stop_pidfile() {
  local pf="$1"
  [ -f "$pf" ] || return 0
  local pid
  pid=$(cat "$pf" 2>/dev/null || true)
  [ -n "$pid" ] || { rm -f "$pf"; return 0; }
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    for _ in 1 2 3 4 5; do
      kill -0 "$pid" 2>/dev/null || break
      sleep 1
    done
    kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$pf"
}

start_opencode() {
  pkill -f 'opencode serve' 2>/dev/null || true
  stop_pidfile "$OC_PIDFILE"
  setsid opencode serve --hostname 127.0.0.1 --port 4096 \
    > "$LOG_DIR/opencode.log" 2>&1 < /dev/null &
  echo $! > "$OC_PIDFILE"
  disown
}

start_bot() {
  pkill -f 'bot.main' 2>/dev/null || true
  stop_pidfile "$BOT_PIDFILE"
  cd "$REPO_DIR"
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
  set -a
  # shellcheck disable=SC1091
  . "$INSTALL_ROOT/.env"
  set +a
  export OPENCODE_SERVER_PASSWORD
  setsid python3 -m bot.main > "$LOG_DIR/bot.out" 2>&1 < /dev/null &
  echo $! > "$BOT_PIDFILE"
  disown
}

case "${1:-start}" in
  start)
    start_opencode
    start_bot
    ;;
  stop)
    stop_pidfile "$BOT_PIDFILE"
    stop_pidfile "$OC_PIDFILE"
    pkill -f 'bot.main' 2>/dev/null || true
    pkill -f 'opencode serve' 2>/dev/null || true
    ;;
  restart)
    "$0" stop
    sleep 1
    "$0" start
    ;;
  *)
    echo "usage: $0 {start|stop|restart}" >&2
    exit 1
    ;;
esac
