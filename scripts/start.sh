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

echo "[*] Starting opencode serve + bot via proot supervisor..."
proot-distro login ubuntu --shared-tmp -- /bin/bash -c "
mkdir -p $LOG_DIR
chmod +x $REPO_DIR/scripts/proot-supervisor.sh
setsid $REPO_DIR/scripts/proot-supervisor.sh start > $LOG_DIR/supervisor.out 2>&1 < /dev/null &
disown
sleep 3
"

sleep 1
echo "[*] Done. Tail logs with:"
echo "    proot-distro login ubuntu -- tail -f $LOG_DIR/bot.out"
echo "    proot-distro login ubuntu -- tail -f $LOG_DIR/opencode.log"

sleep 2
echo "[*] Done. Tail logs with:"
echo "    proot-distro login ubuntu -- tail -f $LOG_DIR/bot.out"
echo "    proot-distro login ubuntu -- tail -f $LOG_DIR/opencode.log"
