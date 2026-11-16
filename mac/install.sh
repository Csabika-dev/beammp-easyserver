#!/bin/bash
# =============================================================================
#  BeamMP EasyServer for macOS (Apple Silicon and Intel Macs, macOS 13+) - EXPERIMENTAL,
#  only in the Rolling release (main branch), not part of Stable yet.
#
#  BeamMP has no macOS server, so EasyServer runs the official Linux server in
#  a small Linux VM (Lima, free and open source) that starts with your Mac.
#  Players connect to your Mac as usual; the Mac passes the game port on to the VM.
#
#  Install / update (paste into Terminal, as your normal user - not sudo):
#    curl -fsSL https://raw.githubusercontent.com/Csabika-dev/beammp-easyserver/main/mac/install.sh | bash
#  Remove everything again:
#    curl -fsSL https://raw.githubusercontent.com/Csabika-dev/beammp-easyserver/main/mac/install.sh | bash -s -- --uninstall
#  Other options are passed on to the Linux installer: --key XXXX --name "My Server" --port 30814 ...
# =============================================================================
set -euo pipefail

EASY_VERSION="1.15.0"
BRANCH="main"            # the stable branch sets this to "stable"
REPO_RAW="https://raw.githubusercontent.com/Csabika-dev/beammp-easyserver/$BRANCH"
VM="easyserver"
ES_HOME="$HOME/.beammp-easyserver"
AGENT_LABEL="com.beammp-easyserver.vm"
AGENT_PLIST="$HOME/Library/LaunchAgents/$AGENT_LABEL.plist"
SHORTCUT="$HOME/Desktop/BeamMP Dashboard.webloc"
DASH_PORT=30815
FWD_FIRST=30814          # game ports (and the dashboard) passed from the Mac to the VM, TCP + UDP
FWD_LAST=30830

if [ -t 1 ]; then B=$'\033[1m'; G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; N=$'\033[0m'; else B=""; G=""; Y=""; R=""; N=""; fi
step() { printf '\n%s==> %s%s\n' "$B" "$1" "$N"; }
ok()   { printf '  %s[OK]%s %s\n' "$G" "$N" "$1"; }
warn() { printf '  %s[!]%s  %s\n' "$Y" "$N" "$1"; }
die()  { printf '\n  %s[X]%s %s\n\n' "$R" "$N" "$1" >&2; exit 1; }
has_tty() { (exec </dev/tty) 2>/dev/null; }   # is someone at the keyboard? (also when piped from curl)
ask() {  # ask "Question" "default" -> echoes the answer
  local a=""
  if has_tty; then read -r -p "  $1 [$2]: " a </dev/tty || true; fi
  echo "${a:-$2}"
}
ask_yn() { local a; a=$(ask "$1 (y/n)" "$2"); case "$a" in [Yy]*) return 0;; *) return 1;; esac; }

MODE="install"; PASS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --uninstall) MODE="uninstall"; shift;;
    --update) MODE="update"; shift;;
    -h|--help) sed -n '2,15p' "$0" 2>/dev/null || true; exit 0;;
    *) PASS+=("$1"); shift;;
  esac
done

[ "$(uname -s)" = "Darwin" ] || die "This installer is for macOS. On Linux use linux/install.sh, on Windows the .bat installer."
[ "$(id -u)" -ne 0 ] || die "Run this as your normal user, not with sudo - it asks for your password only when it needs it."
MACOS_MAJOR=$(sw_vers -productVersion | cut -d. -f1)
[ "$MACOS_MAJOR" -ge 13 ] || die "macOS 13 (Ventura) or newer is needed. This Mac has $(sw_vers -productVersion)."

# ---- helpers -----------------------------------------------------------------
brew_bin() { command -v brew 2>/dev/null || { [ -x /opt/homebrew/bin/brew ] && echo /opt/homebrew/bin/brew; } || { [ -x /usr/local/bin/brew ] && echo /usr/local/bin/brew; } || true; }
mac_ip() {  # this Mac's address on the home network (Ethernet or Wi-Fi, whichever has the default route)
  local ifc ip
  ifc=$(route -n get default 2>/dev/null | awk '/interface:/ {print $2; exit}')
  ip=""; [ -n "$ifc" ] && ip=$(ipconfig getifaddr "$ifc" 2>/dev/null || true)
  [ -n "$ip" ] || ip=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)
  echo "$ip"
}
vm_status() { limactl list --format '{{.Status}}' "$VM" 2>/dev/null || true; }
game_port() {  # the port from the server's config inside the VM (falls back to 30814)
  local p
  p=$(limactl shell --workdir / "$VM" -- sudo cat /opt/beammp-server/ServerConfig.toml 2>/dev/null </dev/null \
      | sed -n 's/^[[:space:]]*Port[[:space:]]*=[[:space:]]*\([0-9][0-9]*\).*/\1/p' | head -1 || true)
  echo "${p:-30814}"
}

# ---- uninstall ---------------------------------------------------------------
if [ "$MODE" = "uninstall" ]; then
  BREW=$(brew_bin); [ -n "$BREW" ] && eval "$("$BREW" shellenv)"
  echo
  echo "  This removes the BeamMP server from this Mac, ${B}including its mods, settings and player stats${N}."
  ask_yn "Remove it?" "n" || { echo "  Nothing was changed."; exit 0; }
  launchctl bootout "gui/$(id -u)/$AGENT_LABEL" 2>/dev/null || true
  rm -f "$AGENT_PLIST" "$SHORTCUT"
  if [ -f "$ES_HOME/config" ] && command -v upnpc >/dev/null; then
    # shellcheck disable=SC1091
    . "$ES_HOME/config"
    for pr in TCP UDP; do upnpc -d "${PORT:-30814}" "$pr" >/dev/null 2>&1 || true; done
  fi
  if command -v limactl >/dev/null && [ -n "$(vm_status)" ]; then limactl delete -f "$VM" >/dev/null 2>&1 || true; fi
  rm -rf "$ES_HOME"
  ok "Removed. (Lima and miniupnpc stay installed - remove them with: brew uninstall lima miniupnpc)"
  exit 0
fi

cat <<EOF

${B}  BeamMP EasyServer $EASY_VERSION for macOS (experimental)${N}
  BeamMP has no Mac server, so this runs the official Linux server in a small
  Linux VM that starts with your Mac (about 2 GB of memory, 20 GB of disk at most).
EOF

# ---- 1. tools ------------------------------------------------------------------
step "Checking the tools"
BREW=$(brew_bin)
if [ -z "$BREW" ]; then
  cat <<EOF

  EasyServer uses ${B}Homebrew${N} (the usual way to install tools on a Mac) to get Lima.
  Install Homebrew first - paste this into Terminal and follow what it says:

    /bin/bash -c "\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

  Then run the EasyServer command again.
EOF
  exit 1
fi
eval "$("$BREW" shellenv)"
need=""; command -v limactl >/dev/null || need="$need lima"; command -v upnpc >/dev/null || need="$need miniupnpc"
if [ -n "$need" ]; then
  echo "  Installing$need with Homebrew (can take a few minutes)..."
  "$BREW" install $need >/dev/null || die "Homebrew couldn't install$need. Run: brew install$need"
fi
LIMA_MAJOR=$(limactl --version 2>/dev/null | sed -E 's/.* ([0-9]+)\..*/\1/' | head -1)
if [ "${LIMA_MAJOR:-0}" -lt 2 ]; then
  echo "  Updating Lima (2.0 or newer is needed for the game's UDP traffic)..."
  "$BREW" upgrade lima >/dev/null || die "Couldn't update Lima. Run: brew upgrade lima"
fi
ok "Lima $(limactl --version | awk '{print $NF}') and miniupnpc are ready"

IP=$(mac_ip)
[ -n "$IP" ] || warn "Couldn't find this Mac's network address - is it connected to your router?"

# ---- 2. friends outside the home -------------------------------------------------
PORTS="manual"
[ -f "$ES_HOME/config" ] && PORTS=$(. "$ES_HOME/config"; echo "${PORTS_CHOICE:-manual}")
if [ "$MODE" = "install" ]; then
  cur=1; [ "$PORTS" = manual ] && [ -f "$ES_HOME/config" ] && cur=2; [ "$PORTS" = later ] && cur=3
  cat <<EOF

  ${B}Letting friends join from anywhere${N}
  Friends on your Wi-Fi can join straight away. Friends somewhere else need your router
  to let them through to this Mac on the game port (this is called port forwarding).

    1) Do it for me (recommended)
       Your Mac asks the router to open the game port for this Mac (UPnP) - no router
       settings page needed. It stays open while the Mac is on and is checked every
       20 minutes. Only the game port is touched. If the router says no, the dashboard's
       Health page tells you and shows how to do it by hand.
    2) I'll do it myself - at the end you get exactly what to type into your router.
    3) Not now - only people on your Wi-Fi can join. Nothing changes on your router.
EOF
  case "$(ask "Choose 1, 2 or 3" "$cur")" in 2) PORTS=manual;; 3) PORTS=later;; *) PORTS=auto;; esac
fi

# ---- 3. the Linux VM -------------------------------------------------------------
step "Starting the Linux VM"
mkdir -p "$ES_HOME"
cat >"$ES_HOME/$VM.yaml" <<EOF
# Made by BeamMP EasyServer. A small Debian VM for the BeamMP server.
base: template://debian-12
cpus: 2
memory: "2GiB"
disk: "20GiB"
mounts: []                      # the VM can't see your Mac's files
containerd:
  system: false
  user: false
portForwards:
# Players and the dashboard reach this Mac; Lima passes TCP and UDP on to the VM.
- guestPortRange: [$FWD_FIRST, $FWD_LAST]
  hostIP: "0.0.0.0"
  proto: any
EOF
case "$(vm_status)" in
  "")       echo "  Downloading Debian and creating the VM (a few minutes the first time)..."
            limactl start --name="$VM" --tty=false "$ES_HOME/$VM.yaml" </dev/null >"$ES_HOME/vm-start.log" 2>&1 \
              || die "The VM didn't start. Details: $ES_HOME/vm-start.log";;
  Running)  ;;
  *)        limactl start "$VM" --tty=false </dev/null >"$ES_HOME/vm-start.log" 2>&1 || die "The VM didn't start. Details: $ES_HOME/vm-start.log";;
esac
ok "Linux VM \"$VM\" is running"

# ---- 4. EasyServer inside the VM -------------------------------------------------------
step "Installing the BeamMP server inside the VM"
LARGS=(--laptop-mode no); [ "$MODE" = "update" ] && LARGS+=(--update)
q=""; for a in ${LARGS[@]+"${LARGS[@]}"} ${PASS[@]+"${PASS[@]}"}; do q="$q $(printf '%q' "$a")"; done
INNER="set -e; curl -fsSL '$REPO_RAW/linux/install.sh' -o /tmp/es-install.sh; sudo env EASY_HOST=mac EASY_MAC_PORTS='$PORTS' EASY_HOST_LAN_IP='$IP' bash /tmp/es-install.sh$q"
if has_tty; then limactl shell --workdir / "$VM" -- bash -c "$INNER" </dev/tty
else limactl shell --workdir / "$VM" -- bash -c "$INNER" </dev/null; fi
PORT=$(game_port)

# ---- 5. start with the Mac, keep the port open -------------------------------------------
step "Starting with your Mac"
cat >"$ES_HOME/config" <<EOF
VM="$VM"
PORT="$PORT"
PORTS_CHOICE="$PORTS"
EOF
cat >"$ES_HOME/agent.sh" <<'AGENT'
#!/bin/bash
# Runs at login and every 20 minutes: keeps the VM running, tells the dashboard this Mac's
# address, and (if chosen) asks the router to keep the game port open to this Mac.
for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do [ -x "$b" ] && eval "$("$b" shellenv)" && break; done
. "$HOME/.beammp-easyserver/config"
st=$(limactl list --format '{{.Status}}' "$VM" 2>/dev/null || true)
[ "$st" = "Running" ] || limactl start "$VM" --tty=false </dev/null >/dev/null 2>&1 || exit 0
ifc=$(route -n get default 2>/dev/null | awk '/interface:/ {print $2; exit}')
IP=""; [ -n "$ifc" ] && IP=$(ipconfig getifaddr "$ifc" 2>/dev/null)
[ -n "$IP" ] || IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null)
upnp="off"; err=""
if [ "$PORTS_CHOICE" = "auto" ] && [ -n "$IP" ]; then
  out=$( { upnpc -e "BeamMP EasyServer" -a "$IP" "$PORT" "$PORT" TCP; upnpc -e "BeamMP EasyServer" -a "$IP" "$PORT" "$PORT" UDP; } 2>&1 )
  if [ "$(printf '%s\n' "$out" | grep -c 'is redirected to')" -ge 2 ]; then upnp="ok"
  else upnp="failed"; err=$(printf '%s\n' "$out" | grep -iE 'no igd|fail|error|conflict' | head -1 | tr -d '"\\' | cut -c1-160)
       [ -n "$err" ] || err="The router didn't answer - UPnP is off or not supported."; fi
fi
printf '{"platform": "mac", "lan_ip": "%s", "ports": "%s", "upnp": "%s", "upnp_error": "%s", "upnp_at": %s, "t": %s}\n' \
  "$IP" "$PORTS_CHOICE" "$upnp" "$err" "$(date +%s)" "$(date +%s)" \
  | limactl shell --workdir / "$VM" -- sudo tee /opt/beammp-server/.easyserver/host.json >/dev/null 2>&1
exit 0
AGENT
chmod +x "$ES_HOME/agent.sh"
mkdir -p "$(dirname "$AGENT_PLIST")"
cat >"$AGENT_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$AGENT_LABEL</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$ES_HOME/agent.sh</string></array>
  <key>RunAtLoad</key><true/>
  <key>StartInterval</key><integer>1200</integer>
  <key>StandardOutPath</key><string>$ES_HOME/agent.log</string>
  <key>StandardErrorPath</key><string>$ES_HOME/agent.log</string>
</dict></plist>
EOF
launchctl bootout "gui/$(id -u)/$AGENT_LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$AGENT_PLIST" 2>/dev/null || launchctl load -w "$AGENT_PLIST" 2>/dev/null || true
/bin/bash "$ES_HOME/agent.sh" || true
ok "The server starts when you log in to this Mac"
cat >"$SHORTCUT" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>URL</key><string>http://localhost:$DASH_PORT</string></dict></plist>
EOF
ok "\"BeamMP Dashboard\" shortcut is on your desktop"

# ---- 6. sleep ------------------------------------------------------------------
if [ "$MODE" = "install" ] && [ "$(pmset -g custom 2>/dev/null | awk '/AC Power/{f=1} f && $1=="sleep" {print $2; exit}')" != "0" ]; then
  echo
  echo "  A sleeping Mac can't host. Players are kicked when it goes to sleep."
  if ask_yn "Keep this Mac awake while it's plugged in? (the screen can still turn off; asks for your password)" "y"; then
    if sudo pmset -c sleep 0 disksleep 0; then ok "This Mac stays awake while plugged in (undo: sudo pmset -c sleep 1)"; else warn "Not changed."; fi
  fi
fi

# ---- 7. done -------------------------------------------------------------------
PUB=$(curl -fsS --max-time 5 https://api.ipify.org 2>/dev/null || echo "unknown")
UP=$(limactl shell --workdir / "$VM" -- cat /opt/beammp-server/.easyserver/host.json 2>/dev/null </dev/null | sed -n 's/.*"upnp": "\([a-z]*\)".*/\1/p')
GW=$(route -n get default 2>/dev/null | awk '/gateway:/ {print $2; exit}')
cat <<EOF

${G}${B}  Done!${N}

  Friends on the same Wi-Fi connect to:  ${B}${IP:-this Mac}:$PORT${N}
  Friends over the internet connect to:  ${B}$PUB:$PORT${N}
EOF
if [ "$PORTS" = "auto" ] && [ "$UP" = "ok" ]; then
  echo "    -> Your router opened port $PORT (TCP + UDP) for this Mac. It's checked every 20 minutes."
elif [ "$PORTS" != "later" ]; then
  [ "$PORTS" = "auto" ] && echo "    ${Y}Your router didn't accept the automatic port opening (UPnP is off or not supported).${N}"
  echo "    -> Set up port forwarding on your router:"
  echo "       1. Open your router's settings page: http://${GW:-192.168.0.1}  (the login is often on a sticker on the router)"
  echo "       2. Find \"Port forwarding\" (sometimes called \"Virtual server\" or \"NAT\")."
  echo "       3. Add a rule: port $PORT - protocol TCP and UDP (or Both) - to ${IP:-this Mac}"
  echo "       4. Save. Test it on the dashboard's Health page."
else
  echo "    -> Not set up yet. Run this installer again and pick \"Do it for me\" when you want it."
fi
cat <<EOF

  If macOS asks whether "limactl" may accept incoming network connections, click ${B}Allow${N} -
  that's how players reach the server.

  Dashboard:  ${B}http://localhost:$DASH_PORT${N} on this Mac (shortcut on your desktop),
              or ${B}http://${IP:-this-mac}:$DASH_PORT${N} from your phone. The password was shown above.
  Update:     run the same command again.   Remove:  ... | bash -s -- --uninstall
  Logs:       $ES_HOME/   ·   Server console:  limactl shell $VM -- sudo journalctl -u beammp-server -f

EOF
