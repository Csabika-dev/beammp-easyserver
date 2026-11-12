#!/usr/bin/env bash
# =============================================================================
#  BeamMP EasyServer - wake helper installer (Raspberry Pi / any Linux with systemd)
#
#  Installs a tiny background service that wakes your BeamMP server computer
#  up (Wake-on-LAN) when you press "Wake up" in the phone app or use /start in
#  Discord while it sleeps. Run it on a device at home that is always on.
#
#    sudo bash install-wake-helper.sh                 # install, asks for the pairing code
#    sudo bash install-wake-helper.sh --code ESW1-... # install without the question
#    sudo bash install-wake-helper.sh --uninstall     # remove it
# =============================================================================
set -euo pipefail

REPO_RAW="https://raw.githubusercontent.com/Csabika-dev/beammp-easyserver/main"
LIB="/usr/local/lib/beammp-wake"
CONF="/etc/beammp-wake"
SVC_USER="beammp-wake"
UNIT="/etc/systemd/system/beammp-wake.service"

ok()   { echo "  [OK] $*"; }
die()  { echo "  [ERROR] $*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "Run it with sudo:  sudo bash $0"
command -v systemctl >/dev/null || die "This needs a Linux with systemd (Raspberry Pi OS, Debian, Ubuntu, ...)"

if [[ "${1:-}" == "--uninstall" ]]; then
  systemctl disable --now beammp-wake.service >/dev/null 2>&1 || true
  rm -f "$UNIT"; systemctl daemon-reload
  rm -rf "$LIB" "$CONF"
  id "$SVC_USER" >/dev/null 2>&1 && userdel "$SVC_USER" 2>/dev/null || true
  ok "Wake helper removed"; exit 0
fi

echo "==> BeamMP wake helper"
if ! command -v python3 >/dev/null; then
  command -v apt-get >/dev/null || die "Please install python3 first"
  apt-get update -qq && apt-get install -y -qq python3 >/dev/null
fi
ok "Python $(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"

# the program: next to this script (from the ZIP) or straight from GitHub
mkdir -p "$LIB"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$here/easyserver_wake.py" ]]; then
  install -m 644 "$here/easyserver_wake.py" "$LIB/easyserver_wake.py"
else
  command -v curl >/dev/null || die "curl is missing (sudo apt install curl)"
  curl -fsSL "$REPO_RAW/wake/easyserver_wake.py" -o "$LIB/easyserver_wake.py.tmp" || die "Download failed"
  head -c 200 "$LIB/easyserver_wake.py.tmp" | grep -q "BeamMP EasyServer - wake helper" || die "The download doesn't look right"
  mv -f "$LIB/easyserver_wake.py.tmp" "$LIB/easyserver_wake.py"; chmod 644 "$LIB/easyserver_wake.py"
fi
python3 -m py_compile "$LIB/easyserver_wake.py" 2>/dev/null || die "This Python is too old (3.7 or newer needed)"
ok "Program installed in $LIB"

# its own user with no rights: it only needs to send network packets
id "$SVC_USER" >/dev/null 2>&1 || useradd --system --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin "$SVC_USER"
mkdir -p "$CONF"; chown "$SVC_USER:$SVC_USER" "$CONF"; chmod 700 "$CONF"

echo
if [[ -r /dev/tty ]]; then
  BEAMMP_WAKE_CONFIG="$CONF/config.json" runuser -u "$SVC_USER" -- python3 "$LIB/easyserver_wake.py" setup "$@" </dev/tty
else
  BEAMMP_WAKE_CONFIG="$CONF/config.json" runuser -u "$SVC_USER" -- python3 "$LIB/easyserver_wake.py" setup --no-token "$@"
fi
[[ -f "$CONF/config.json" ]] || die "Setup didn't finish"

cat >"$UNIT" <<EOF
[Unit]
Description=BeamMP EasyServer wake helper
Wants=network-online.target
After=network-online.target

[Service]
User=$SVC_USER
Environment=BEAMMP_WAKE_CONFIG=$CONF/config.json
ExecStart=/usr/bin/env python3 $LIB/easyserver_wake.py run
Restart=always
RestartSec=10
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
CapabilityBoundingSet=
ReadOnlyPaths=$CONF

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable beammp-wake.service >/dev/null 2>&1
systemctl restart beammp-wake.service
sleep 3
systemctl is-active --quiet beammp-wake.service || { journalctl -u beammp-wake -n 20 --no-pager; die "The helper didn't start"; }
ok "Wake helper is running and starts by itself after a reboot"
echo
echo "  Now press 'Test the helper' in the dashboard (Settings -> Sleep & wake-up)."
echo "  Log:            journalctl -u beammp-wake -f"
echo "  Wake it by hand: sudo -u $SVC_USER BEAMMP_WAKE_CONFIG=$CONF/config.json python3 $LIB/easyserver_wake.py wake"
echo "  Remove:         sudo bash $0 --uninstall"
