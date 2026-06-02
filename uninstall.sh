#!/data/data/com.termux/files/usr/bin/bash
set -e

TERMUX_INSTALL_ROOT="$HOME/.opencode-telegram-termux"
PROOT_INSTALL_ROOT="/root/.opencode-telegram"

echo "[*] Stopping services..."
proot-distro login ubuntu --shared-tmp -- /bin/bash -c "
  pkill -f 'bot/main.py' 2>/dev/null || true
  pkill -f 'opencode serve' 2>/dev/null || true
  crontab -r 2>/dev/null || true
" || true

rm -f "$HOME/.termux/boot/opencode-telegram.sh"
rm -rf "$TERMUX_INSTALL_ROOT"
proot-distro login ubuntu --shared-tmp -- /bin/bash -c "rm -rf $PROOT_INSTALL_ROOT" || true

echo "[*] Done. To fully remove proot Ubuntu, run:"
echo "    proot-distro remove ubuntu"
