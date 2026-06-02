#!/data/data/com.termux/files/usr/bin/bash
set -e

INSTALL_ROOT="/root/.opencode-telegram"
REPO_DIR="$INSTALL_ROOT/repo"
VENV="$INSTALL_ROOT/venv"
LOG_DIR="$INSTALL_ROOT/logs"
PIDFILE="$INSTALL_ROOT/bot.pid"
OC_PIDFILE="$INSTALL_ROOT/opencode.pid"

echo "[*] Acquiring Termux wake lock..."
termux-wake-lock || true

echo "[*] Starting cron daemon inside proot Ubuntu..."
proot-distro login ubuntu --shared-tmp -- /bin/bash -c "mkdir -p $LOG_DIR && service cron start 2>/dev/null || cron"

echo "[*] Starting opencode serve in background..."
proot-distro login ubuntu --shared-tmp -- /bin/bash -c "
mkdir -p $LOG_DIR
set -a
. $INSTALL_ROOT/.env
set +a
export OPENCODE_SERVER_PASSWORD
setsid nohup opencode serve --hostname 127.0.0.1 --port 4096 \
  > $LOG_DIR/opencode.log 2>&1 < /dev/null &
echo \$! > $OC_PIDFILE
disown
sleep 2
"

echo "[*] Starting Telegram bot..."
proot-distro login ubuntu --shared-tmp -- /bin/bash -c "
mkdir -p $LOG_DIR
cd $REPO_DIR
source $VENV/bin/activate
export TELEGRAM_BOT_TOKEN TELEGRAM_ALLOWED_USER_ID OPENCODE_SERVER_PASSWORD
setsid nohup python3 -m bot.main > $LOG_DIR/bot.out 2>&1 < /dev/null &
echo \$! > $PIDFILE
disown
"

sleep 2
echo "[*] Done. Tail logs with:"
echo "    proot-distro login ubuntu -- tail -f $LOG_DIR/bot.out"
echo "    proot-distro login ubuntu -- tail -f $LOG_DIR/opencode.log"
