#!/data/data/com.termux/files/usr/bin/bash
set -e

REPO_URL="${REPO_URL:-https://github.com/Bolol4002/opencode-telegram-server.git}"
BRANCH="${BRANCH:-main}"
TERMUX_INSTALL_ROOT="$HOME/.opencode-telegram-termux"
PROOT_INSTALL_ROOT="/root/.opencode-telegram"

clear
cat <<'BANNER'
================================================================
   OpenCode Telegram Server - Installer
   https://github.com/anomalyco/opencode
================================================================
BANNER

echo
echo "[*] Checking environment..."

if [ -z "$PREFIX" ] || [ "$PREFIX" != "/data/data/com.termux/files/usr" ]; then
  echo "[!] This installer must run inside Termux on Android."
  echo "    Install 'Termux' from F-Droid, then re-run this script."
  exit 1
fi

echo "[*] Updating Termux packages..."
pkg update -y
pkg upgrade -y

echo "[*] Installing Termux dependencies..."
pkg install -y proot-distro git python openssl

echo "[*] Installing Ubuntu via proot..."
if ! proot-distro list 2>/dev/null | grep -q ubuntu; then
  proot-distro install ubuntu
else
  echo "    Ubuntu already installed, skipping."
fi

echo "[*] Cloning repo into Termux home (for Termux-side scripts)..."
mkdir -p "$TERMUX_INSTALL_ROOT"
if [ -d "$TERMUX_INSTALL_ROOT/repo/.git" ]; then
  git -C "$TERMUX_INSTALL_ROOT/repo" pull --ff-only || true
else
  git clone --depth 1 -b "$BRANCH" "$REPO_URL" "$TERMUX_INSTALL_ROOT/repo"
fi

echo "[*] Bootstrapping Ubuntu environment (this can take a few minutes)..."
proot-distro login ubuntu --shared-tmp -- /bin/bash -c "
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3 python3-pip python3-venv git curl cron nano ca-certificates openssl

mkdir -p $PROOT_INSTALL_ROOT

cd $PROOT_INSTALL_ROOT
if [ -d repo/.git ]; then
  cd repo && git pull --ff-only || true
else
  git clone --depth 1 -b $BRANCH $REPO_URL repo
fi
cd $PROOT_INSTALL_ROOT/repo

python3 -m venv $PROOT_INSTALL_ROOT/venv
source $PROOT_INSTALL_ROOT/venv/bin/activate
pip install --upgrade pip wheel
pip install -r requirements.txt
"

cp "$TERMUX_INSTALL_ROOT/repo/scripts/start.sh" "$TERMUX_INSTALL_ROOT/start.sh"
cp "$TERMUX_INSTALL_ROOT/repo/scripts/stop.sh"  "$TERMUX_INSTALL_ROOT/stop.sh"
cp "$TERMUX_INSTALL_ROOT/repo/scripts/boot.sh"  "$TERMUX_INSTALL_ROOT/boot.sh"
chmod +x "$TERMUX_INSTALL_ROOT/start.sh" "$TERMUX_INSTALL_ROOT/stop.sh"

echo
echo "================================================================"
echo " Base install complete."
echo " Now launching the TUI installer..."
echo "================================================================"
echo

proot-distro login ubuntu --shared-tmp -- /bin/bash -c "
source $PROOT_INSTALL_ROOT/venv/bin/activate
cd $PROOT_INSTALL_ROOT/repo
python3 tui/installer.py
"

echo
echo "[*] Installing Termux:Boot autostart hook..."
mkdir -p "$HOME/.termux/boot"
cp "$TERMUX_INSTALL_ROOT/repo/scripts/boot.sh" "$HOME/.termux/boot/opencode-telegram.sh"
chmod +x "$HOME/.termux/boot/opencode-telegram.sh"
step "Installed: $HOME/.termux/boot/opencode-telegram.sh" 2>/dev/null || \
  echo "    Installed: $HOME/.termux/boot/opencode-telegram.sh"
