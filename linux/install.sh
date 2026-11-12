#!/usr/bin/env bash
# =============================================================================
#  BeamMP EasyServer - Linux installer
#  One script that preps the machine and installs a BeamMP server as a
#  background service that starts on boot.
#
#  Usage:
#    sudo bash install.sh                 # interactive wizard
#    sudo bash install.sh --key XXXX      # skip the key question
#    sudo bash install.sh --unattended --key XXXX --name "My Server"
#    sudo bash install.sh --update        # update server binary only
#    sudo bash install.sh --uninstall     # remove everything
#
#  Not affiliated with the BeamMP team. BeamMP: https://beammp.com
# =============================================================================
set -euo pipefail

EASY_VERSION="1.12.0"
INSTALL_DIR="/opt/beammp-server"
SERVICE_USER="beammp"
DASH_USER="beammp-dash"
SERVICE_NAME="beammp-server"
HELPER="/usr/local/bin/beammp"
LOGIND_DROPIN="/etc/systemd/logind.conf.d/99-beammp-easyserver.conf"
RELEASE_BASE="https://github.com/BeamMP/BeamMP-Server/releases/latest/download"
# Where the extra files (mod page, virus scanner) are downloaded from when this
# script is run with "curl ... | sudo bash" instead of from the downloaded ZIP:
REPO_RAW="https://raw.githubusercontent.com/Csabika-dev/beammp-easyserver/main"
# Root-owned locations (the "beammp" user must never be able to change these)
ES_DIR="/usr/local/lib/beammp-easyserver"     # scripts
SECRETS_KEY_DIR="/etc/beammp-easyserver"       # unlock key + settings
STATE_DIR="/var/lib/beammp-easyserver"         # encrypted keys
DATA_DIR="$INSTALL_DIR/.easyserver"            # scan cache (written by beammp)
KEYMASTER_URL="https://keymaster.beammp.com"

# ---- defaults (can be overridden by flags) ----------------------------------
OPT_KEY=""
OPT_NAME=""
OPT_MAP=""
OPT_PLAYERS=""
OPT_CARS=""
OPT_PORT=""
OPT_PRIVATE=""
OPT_LAPTOP=""        # yes / no / "" (= ask)
OPT_MODPAGE=""       # yes / no / "" (= ask)
OPT_VTKEY=""         # VirusTotal API key (optional)
MODS_PORT=30815
OPT_UNATTENDED=0
MODE="install"
ORIG_ARGS=("$@")

# ---- pretty output -----------------------------------------------------------
if [[ -t 1 ]]; then
  C_RESET=$'\e[0m'; C_BOLD=$'\e[1m'; C_GREEN=$'\e[32m'; C_YELLOW=$'\e[33m'
  C_RED=$'\e[31m'; C_CYAN=$'\e[36m'
else
  C_RESET=""; C_BOLD=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_CYAN=""
fi
step() { echo; echo "${C_CYAN}${C_BOLD}==> $*${C_RESET}"; }
ok()   { echo "${C_GREEN}  [OK]${C_RESET} $*"; }
warn() { echo "${C_YELLOW}  [!]${C_RESET} $*"; }
die()  { echo "${C_RED}${C_BOLD}  [ERROR]${C_RESET} $*" >&2; pause_if_terminal; exit 1; }

pause_if_terminal() {
  # Keeps the window open when the script was started by double-clicking.
  if [[ $OPT_UNATTENDED -eq 0 && -t 0 ]]; then
    read -r -p "Press Enter to close..." _ </dev/tty || true
  fi
}

# Read from the real keyboard even when piped through "curl | sudo bash".
ask() { # ask "Question" "default" -> echoes answer
  local q="$1" def="${2:-}" ans=""
  if [[ $OPT_UNATTENDED -eq 1 || ! -r /dev/tty ]]; then echo "$def"; return; fi
  if [[ -n "$def" ]]; then
    read -r -p "  $q [${def}]: " ans </dev/tty || true
  else
    read -r -p "  $q: " ans </dev/tty || true
  fi
  echo "${ans:-$def}"
}
ask_yn() { # ask_yn "Question" Y|N -> returns 0 for yes
  local q="$1" def="${2:-Y}" ans
  ans=$(ask "$q (y/n)" "$def")
  [[ "$ans" =~ ^[Yy] ]]
}

usage() {
  sed -n '2,16p' "$0" 2>/dev/null | sed 's/^# \{0,1\}//'
  cat <<EOF
Options:
  --key KEY          BeamMP AuthKey (get one at $KEYMASTER_URL)
  --name NAME        Server name
  --map MAP          Map folder name, e.g. gridmap_v2, west_coast_usa, italy
  --players N        Max players (default 8)
  --cars N           Max cars per player (default 1)
  --port N           Port (default 30814)
  --public / --private   Show / hide the server in the public server list
  --laptop-mode yes|no   Keep running with the lid closed, never sleep
  --mod-page yes|no      Drag & drop mod upload web page (port $MODS_PORT)
  --virustotal KEY       VirusTotal API key for the mod virus check (optional)
  --unattended       Don't ask any questions, use defaults/flags
  --update           Only download the newest server version
  --uninstall        Remove the server, service and settings
  -h, --help         Show this help
EOF
}

# ---- parse flags -------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --key) OPT_KEY="${2:-}"; shift 2;;
    --name) OPT_NAME="${2:-}"; shift 2;;
    --map) OPT_MAP="${2:-}"; shift 2;;
    --players) OPT_PLAYERS="${2:-}"; shift 2;;
    --cars) OPT_CARS="${2:-}"; shift 2;;
    --port) OPT_PORT="${2:-}"; shift 2;;
    --public) OPT_PRIVATE="false"; shift;;
    --private) OPT_PRIVATE="true"; shift;;
    --laptop-mode) OPT_LAPTOP="${2:-}"; shift 2;;
    --mod-page) OPT_MODPAGE="${2:-}"; shift 2;;
    --virustotal) OPT_VTKEY="${2:-}"; shift 2;;
    --unattended|-y) OPT_UNATTENDED=1; shift;;
    --update) MODE="update"; shift;;
    --uninstall) MODE="uninstall"; shift;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown option: $1"; usage; exit 1;;
  esac
done

# ---- become root -------------------------------------------------------------
if [[ $EUID -ne 0 ]]; then
  if [[ -f "${BASH_SOURCE[0]:-}" ]]; then
    echo "Administrator rights are needed. Enter your password:"
    exec sudo bash "$(readlink -f "${BASH_SOURCE[0]}")" ${ORIG_ARGS[@]+"${ORIG_ARGS[@]}"}
  fi
  die "Please run with sudo:  curl -fsSL <url>/install.sh | sudo bash"
fi

command -v systemctl >/dev/null || die "This installer needs systemd (Ubuntu, Mint, Debian, Fedora, Arch... all have it)."

# ---- detect system -----------------------------------------------------------
detect_system() {
  [[ -r /etc/os-release ]] || die "Cannot detect your Linux version (/etc/os-release missing)."
  # shellcheck disable=SC1091
  . /etc/os-release
  OS_PRETTY="${PRETTY_NAME:-Linux}"

  case "$(uname -m)" in
    x86_64|amd64) ARCH="x86_64";;
    aarch64|arm64) ARCH="arm64";;
    *) die "Your CPU type ($(uname -m)) has no official BeamMP server build. Needs 64-bit x86 or ARM64.";;
  esac

  PKG=""
  command -v apt-get >/dev/null && PKG="apt"
  [[ -z "$PKG" ]] && command -v dnf >/dev/null && PKG="dnf"
  [[ -z "$PKG" ]] && command -v pacman >/dev/null && PKG="pacman"
  [[ -z "$PKG" ]] && command -v zypper >/dev/null && PKG="zypper"

  local ubuntu_cn="${UBUNTU_CODENAME:-}" debian_cn="${DEBIAN_CODENAME:-}"
  [[ -z "$ubuntu_cn" && "${ID:-}" == "ubuntu" ]] && ubuntu_cn="${VERSION_CODENAME:-}"
  [[ -z "$debian_cn" && "${ID:-}" == "debian" ]] && debian_cn="${VERSION_CODENAME:-}"
  # LMDE and other Debian-based distros without the variables above
  if [[ -z "$ubuntu_cn" && -z "$debian_cn" && -r /etc/debian_version ]]; then
    case "$(cut -d. -f1 /etc/debian_version)" in
      12|bookworm*) debian_cn="bookworm";;
      13|trixie*) debian_cn="trixie";;
      *) debian_cn="$(cut -d/ -f1 /etc/debian_version)";;
    esac
  fi

  SUPPORT="official"
  if [[ -n "$ubuntu_cn" ]]; then
    case "$ubuntu_cn" in
      trusty|xenial|bionic|focal)
        die "$OS_PRETTY is too old for the BeamMP server. Use Ubuntu 22.04+ / Linux Mint 21+.";;
      jammy) DISTRO="ubuntu.22.04";;
      *) DISTRO="ubuntu.24.04";;   # noble and anything newer
    esac
  elif [[ -n "$debian_cn" ]]; then
    case "$debian_cn" in
      buster|bullseye|10*|11*) die "$OS_PRETTY is too old. Use Debian 12+ / LMDE 6+.";;
      bookworm) DISTRO="debian.12";;
      *) DISTRO="debian.13";;      # trixie and newer
    esac
  else
    DISTRO="ubuntu.24.04"
    SUPPORT="best-effort"
  fi
  ASSET="BeamMP-Server.${DISTRO}.${ARCH}"
}

# ---- dependencies ------------------------------------------------------------
install_deps() {
  step "Installing what the server needs"
  case "$PKG" in
    apt)
      export DEBIAN_FRONTEND=noninteractive
      apt-get update -qq || warn "apt update had problems, continuing anyway"
      apt-get install -y -qq curl ca-certificates liblua5.3-0 python3 openssl util-linux ethtool >/dev/null
      ;;
    dnf)    dnf install -y -q curl ca-certificates python3 openssl compat-lua-libs || dnf install -y -q curl python3 openssl lua;;
    pacman) pacman -Sy --noconfirm --needed curl ca-certificates python openssl lua53;;
    zypper) zypper --non-interactive install curl ca-certificates python3 openssl liblua5_3-5 || true;;
    *) warn "Unknown package manager - make sure curl and Lua 5.3 are installed.";;
  esac
  command -v curl >/dev/null || die "curl could not be installed."
  command -v openssl >/dev/null || die "openssl could not be installed (needed to encrypt your keys)."
  command -v setpriv >/dev/null || die "setpriv (util-linux) is missing."
  ok "Dependencies installed"
}

# Some distros name the Lua 5.3 library differently - make the server find it.
fix_lua_link() {
  local bin="$INSTALL_DIR/BeamMP-Server"
  command -v ldd >/dev/null || return 0
  local libs
  libs=$(ldd "$bin" 2>&1 || true)
  if [[ "$libs" == *"liblua5.3.so.0 => not found"* ]]; then
    local found
    found=$(find /usr/lib /usr/lib64 /usr/local/lib -maxdepth 3 \
      \( -name 'liblua5.3.so*' -o -name 'liblua-5.3.so*' \) 2>/dev/null | head -n1 || true)
    if [[ -n "$found" ]]; then
      ln -sf "$found" /usr/local/lib/liblua5.3.so.0
      ldconfig || true
      ok "Linked Lua library ($found)"
    fi
  fi
  libs=$(ldd "$bin" 2>&1 || true)
  if [[ "$libs" == *"not found"* ]]; then
    warn "Some libraries are missing:"
    grep "not found" <<<"$libs" | sed 's/^/      /'
    warn "The server may not start. Please open an issue on GitHub with the lines above."
  fi
}

# ---- download ----------------------------------------------------------------
download_server() {
  step "Downloading the latest BeamMP server ($ASSET)"
  local tmp
  tmp=$(mktemp)
  if ! curl -fL --retry 3 --connect-timeout 15 --progress-bar \
        -o "$tmp" "$RELEASE_BASE/$ASSET"; then
    rm -f "$tmp"
    die "Download failed. Check your internet connection."
  fi
  install -m 0755 -o "$SERVICE_USER" -g "$SERVICE_USER" "$tmp" "$INSTALL_DIR/BeamMP-Server"
  rm -f "$tmp"
  ok "Server downloaded"
}

# ---- extra files from the repo -----------------------------------------------
SCRIPT_DIR=""
if [[ -n "${BASH_SOURCE[0]:-}" && -f "${BASH_SOURCE[0]}" ]]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi
fetch_file() { # fetch_file REPO/PATH DEST - from the downloaded ZIP, or from GitHub
  local rel="$1" c t
  if [[ -n "$SCRIPT_DIR" ]]; then
    for c in "$SCRIPT_DIR/$rel" "$SCRIPT_DIR/../$rel" "$SCRIPT_DIR/$(basename "$rel")"; do
      if [[ -f "$c" ]]; then install -m 0644 "$c" "$2"; return 0; fi
    done
  fi
  # download to a private temp file; "install" replaces a link instead of following it
  t=$(mktemp)
  curl -fsSL --retry 3 -o "$t" "$REPO_RAW/$rel" || { rm -f "$t"; die "Could not download $rel from $REPO_RAW"; }
  install -m 0644 "$t" "$2"; rm -f "$t"
}

drop_links() { # paths root writes to inside the server folder must be real files/folders
  local p
  for p in "$INSTALL_DIR/ServerConfig.toml" "$INSTALL_DIR/BeamMP-Server" "$INSTALL_DIR/servers" \
           "$INSTALL_DIR/.easyserver" "$INSTALL_DIR/Resources" "$INSTALL_DIR/Resources/Client" \
           "$INSTALL_DIR/Resources/Client-disabled" "$INSTALL_DIR/Resources/Quarantine" \
           "$INSTALL_DIR/Resources/.uploading" "$INSTALL_DIR/Resources/Server" \
           "$INSTALL_DIR/Resources/Server/EasyServerStats" \
           "$INSTALL_DIR/Resources/Server/EasyServerStats/main.lua" \
           "$INSTALL_DIR/.easyserver/dashboard.json"; do
    if [[ -L "$p" ]]; then rm -f "$p"; warn "Removed an unexpected link: $p"; fi
  done
}

# ---- encrypted key storage -----------------------------------------------------
# Your BeamMP AuthKey, VirusTotal key and mod page password are stored
# AES-256 encrypted in $STATE_DIR/secrets.enc. The unlock key is a separate
# file in $SECRETS_KEY_DIR. Both are readable by root only. Keys are only
# decrypted in memory when a program starts - never written to ServerConfig.toml.
setup_secrets() {
  mkdir -p "$ES_DIR" "$SECRETS_KEY_DIR" "$STATE_DIR" "$DATA_DIR"
  chown root:root "$ES_DIR" "$SECRETS_KEY_DIR" "$STATE_DIR"
  chmod 755 "$ES_DIR" "$SECRETS_KEY_DIR"; chmod 700 "$STATE_DIR"
  chown "$DASH_USER:$DASH_USER" "$DATA_DIR"; chmod 750 "$DATA_DIR"
  if [[ ! -s "$SECRETS_KEY_DIR/master.key" ]]; then
    ( umask 077; openssl rand -hex 32 >"$SECRETS_KEY_DIR/master.key" )
  fi
  chmod 600 "$SECRETS_KEY_DIR/master.key"

  cat >"$ES_DIR/secrets.sh" <<'SECRETS_EOF'
#!/usr/bin/env bash
# BeamMP EasyServer encrypted key store (root only).
#   secrets.sh get NAME          print a value
#   secrets.sh set NAME          read the value from stdin and store it encrypted
#   secrets.sh unset NAME
#   secrets.sh has NAME          exit 0 if set
set -euo pipefail
umask 077
KEY=/etc/beammp-easyserver/master.key
STORE=/var/lib/beammp-easyserver/secrets.enc
[[ $EUID -eq 0 ]] || { echo "secrets.sh must run as root" >&2; exit 1; }
[[ -s $KEY ]] || { echo "missing $KEY" >&2; exit 1; }
dec() { [[ -s $STORE ]] && openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass "file:$KEY" -in "$STORE" || true; }
enc() { openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass "file:$KEY" -out "$STORE.tmp"; chmod 600 "$STORE.tmp"; mv -f "$STORE.tmp" "$STORE"; }
name_ok() { [[ "${1:-}" =~ ^[A-Z_][A-Z0-9_]*$ ]] || { echo "bad name" >&2; exit 1; }; }
case "${1:-}" in
  get)   name_ok "${2:-}"; dec | sed -n "s/^$2=//p" | head -n1 | base64 -d 2>/dev/null || true;;
  has)   name_ok "${2:-}"; dec | grep -q "^$2=";;
  set)   name_ok "${2:-}"; IFS= read -r val || true
         val="${val//$'\r'/}"
         { dec | grep -v "^$2=" || true; printf '%s=%s\n' "$2" "$(printf '%s' "$val" | base64 -w0)"; } | enc;;
  unset) name_ok "${2:-}"; { dec | grep -v "^$2=" || true; } | enc;;
  *)     echo "usage: secrets.sh get|set|unset|has NAME" >&2; exit 1;;
esac
SECRETS_EOF
  chown root:root "$ES_DIR/secrets.sh"; chmod 700 "$ES_DIR/secrets.sh"

  # Starts the server / mod page as the beammp user with the keys in memory only
  cat >"$ES_DIR/launch.sh" <<'LAUNCH_EOF'
#!/usr/bin/env bash
# Started by systemd as root: decrypts keys into memory, then drops to an
# unprivileged user ("beammp" for the game server, "beammp-dash" for the
# dashboard). Keys never touch the disk unencrypted.
set -euo pipefail
DIR=/opt/beammp-server; ES=/usr/local/lib/beammp-easyserver
SEC() { "$ES/secrets.sh" get "$1" 2>/dev/null || true; }
AS_SERVER=(setpriv --reuid=beammp --regid=beammp --init-groups --)
AS_DASH=(setpriv --reuid=beammp-dash --regid=beammp-dash --init-groups --)
export HOME=$DIR PATH=/usr/local/bin:/usr/bin:/bin LANG=C.UTF-8 BEAMMP_DIR=$DIR
export MODSCAN_CACHE=$DIR/.easyserver/scancache.json
case "${1:-}" in
  server)
    # "launch.sh server" = main server, "launch.sh server <id>" = extra server in servers/<id>
    ID="${2:-main}"; KEYNAME=BEAMMP_AUTH_KEY
    if [[ "$ID" != "main" ]]; then
      [[ "$ID" =~ ^[a-z0-9]{1,12}$ && -d "$DIR/servers/$ID" && ! -L "$DIR/servers/$ID" ]] || { echo "unknown server $ID" >&2; exit 1; }
      DIR="$DIR/servers/$ID"; KEYNAME="BEAMMP_AUTH_KEY_${ID^^}"
    elif [[ ! "$ID" =~ ^[a-z0-9]{1,12}$ ]]; then echo "bad server id" >&2; exit 1
    fi
    export HOME=$DIR
    # upload (mod download) speed limits - re-applied because the port may have changed
    python3 "$ES/control.py" --shape >/dev/null 2>&1 || true
    # safety check of all mods before players can download them
    v=$(SEC VT_API_KEY); [[ -n "$v" ]] && export VT_API_KEY="$v"
    "${AS_DASH[@]}" python3 "$ES/dashboard/modscan.py" --sweep "$DIR/Resources/Client" "$DIR/Resources/Quarantine" || true
    unset VT_API_KEY
    # The BeamMP server rewrites its config file (including the AuthKey) when
    # it starts. So it gets a copy in /run, which is RAM only and vanishes on
    # reboot - the real ServerConfig.toml never contains the key.
    # Security: the folder above is owned by root, so the game server user can
    # never swap files in it for links; root never opens a file in a folder
    # the game server controls - reading and writing is done as "beammp".
    BASE=/run/beammp-easyserver; RUN="$BASE/$ID"
    if [[ -L "$BASE" || ( -e "$BASE" && "$(stat -c %u "$BASE")" != 0 ) ]]; then rm -rf --one-file-system "$BASE"; fi
    mkdir -p "$BASE"; chown root:root "$BASE"; chmod 755 "$BASE"
    rm -rf --one-file-system "$RUN"; mkdir -m 700 "$RUN"; chown beammp:beammp "$RUN"
    cfg=$("${AS_SERVER[@]}" timeout 10 head -c 262144 -- "$DIR/ServerConfig.toml") || { echo "cannot read $DIR/ServerConfig.toml" >&2; exit 1; }
    v=$(SEC "$KEYNAME"); [[ "$v" =~ ^[A-Za-z0-9-]+$ ]] || v=""
    out=""
    while IFS= read -r line || [[ -n "$line" ]]; do
      if [[ -n "$v" && "$line" =~ ^[[:space:]]*AuthKey[[:space:]]*= ]]; then line="AuthKey = \"$v\""
      # no IPv6 on this machine? listen on IPv4 instead of "::"
      elif [[ ! -e /proc/net/if_inet6 && "$line" =~ ^[[:space:]]*IP[[:space:]]*= ]]; then line='IP = "0.0.0.0"'
      fi
      out+="$line"$'\n'
    done <<<"$cfg"
    unset v cfg
    # printf is a shell builtin: the key never shows up in a process list
    printf '%s' "$out" | "${AS_SERVER[@]}" sh -c 'umask 077; cat > "$1"' sh "$RUN/ServerConfig.toml"
    unset out
    cd "$DIR"
    exec "${AS_SERVER[@]}" /opt/beammp-server/BeamMP-Server --config="$RUN/ServerConfig.toml" ;;
  dashboard|mods)
    for n in MODS_PASSWORD VT_API_KEY DISCORD_WEBHOOK SMTP_PASSWORD TOTP_SECRET DISCORD_BOT_TOKEN DUCKDNS_TOKEN NTFY_TOPIC WAKE_TOPIC USERS_KEY TELEGRAM_TOKEN CUSTOM_WEBHOOK; do
      v=$(SEC "$n"); [[ -n "$v" ]] && export "$n=$v"
    done
    unset v
    if "$ES/secrets.sh" has BEAMMP_AUTH_KEY; then export HAS_AUTH_KEY=1; fi
    # request/answer folders for the root helper (RAM only)
    mkdir -p /run/beammp-easyserver-ctl /run/beammp-easyserver-ctl-out
    chown beammp-dash:beammp-dash /run/beammp-easyserver-ctl; chmod 700 /run/beammp-easyserver-ctl
    chown root:root /run/beammp-easyserver-ctl-out; chmod 755 /run/beammp-easyserver-ctl-out
    cd "$DIR"
    umask 0002
    exec "${AS_DASH[@]}" python3 "$ES/dashboard/dashboard.py" ;;
  *) echo "usage: launch.sh server|dashboard" >&2; exit 1 ;;
esac
LAUNCH_EOF
  chown root:root "$ES_DIR/launch.sh"; chmod 700 "$ES_DIR/launch.sh"
}

secret_set() { printf '%s\n' "$2" | "$ES_DIR/secrets.sh" set "$1"; }
mask() { local v="$1"; (( ${#v} > 6 )) && echo "****${v: -4}" || echo "****"; }

# Hidden input (doesn't show on screen)
ask_secret() {
  local q="$1" ans=""
  if [[ $OPT_UNATTENDED -eq 1 || ! -r /dev/tty ]]; then echo ""; return; fi
  read -r -s -p "  $q: " ans </dev/tty || true
  echo >&2
  echo "$ans"
}

# ---- configuration -----------------------------------------------------------
MAPS=(gridmap_v2 west_coast_usa east_coast_usa utah italy jungle_rock_island
      industrial small_island automation_test_track hirochi_raceway
      johnson_valley derby driver_training)

toml_escape() { local s="$1"; s="${s//\\/\\\\}"; s="${s//\"/\\\"}"; printf '%s' "$s"; }

configure() {
  local cfg="$INSTALL_DIR/ServerConfig.toml"
  # move an old plain-text AuthKey into the encrypted store
  if [[ -f "$cfg" ]]; then
    local oldkey
    oldkey=$(sed -n -E 's/^\s*AuthKey\s*=\s*"([^"]+)".*/\1/p' "$cfg" | head -n1)
    if [[ -n "$oldkey" ]]; then
      secret_set BEAMMP_AUTH_KEY "$oldkey"
      sed -i -E 's/^(\s*AuthKey\s*=\s*)".*"/\1"" # stored encrypted - change with: sudo beammp key/' "$cfg"
      ok "Moved your AuthKey out of ServerConfig.toml into encrypted storage"
    fi
  fi
  if [[ -f "$cfg" ]]; then
    if ! ask_yn "A server config already exists. Set it up again?" N; then
      ok "Keeping your existing settings"
      PORT=$(grep -E '^\s*Port\s*=' "$cfg" | head -n1 | grep -oE '[0-9]+' || echo 30814)
      return
    fi
  fi

  step "Server settings (press Enter to accept the value in [brackets])"
  local key="$OPT_KEY"
  if [[ -z "$key" ]]; then
    echo "  You need a free AuthKey so players can find and join your server."
    echo "  1) Open ${C_BOLD}$KEYMASTER_URL${C_RESET} and log in with Discord"
    echo "  2) Click 'Keys' -> '+' , give it a name, copy the key"
    echo "  (It's stored encrypted. Typing/pasting is hidden - just paste and press Enter.)"
    key=$(ask_secret "Paste your AuthKey here (or leave empty and add it later)")
  fi
  key="${key//[[:space:]]/}"
  if [[ -n "$key" && ! "$key" =~ ^[A-Za-z0-9-]+$ ]]; then
    warn "That AuthKey has unexpected characters - skipped. Add it later: sudo beammp key"; key=""
  fi
  if [[ -n "$key" ]]; then
    secret_set BEAMMP_AUTH_KEY "$key"
    ok "AuthKey saved encrypted ($(mask "$key"))"
  fi

  local name="${OPT_NAME:-$(ask "Server name" "$(hostname) BeamMP Server")}"

  local map="$OPT_MAP"
  if [[ -z "$map" ]]; then
    echo "  Maps:"
    local i=1
    for m in "${MAPS[@]}"; do printf "    %2d) %s\n" "$i" "$m"; i=$((i+1)); done
    local pick
    pick=$(ask "Pick a map number (or type a mod map folder name)" "1")
    if [[ "$pick" =~ ^[0-9]+$ ]] && (( pick >= 1 && pick <= ${#MAPS[@]} )); then
      map="${MAPS[$((pick-1))]}"
    else
      map="$pick"
    fi
  fi

  local players="${OPT_PLAYERS:-$(ask "Max players" "8")}"
  local cars="${OPT_CARS:-$(ask "Max cars per player" "1")}"
  PORT="${OPT_PORT:-$(ask "Port" "30814")}"
  local private="$OPT_PRIVATE"
  if [[ -z "$private" ]]; then
    if ask_yn "Show the server in the public BeamMP server list?" Y; then private="false"; else private="true"; fi
  fi
  [[ "$players" =~ ^[0-9]+$ ]] || players=8
  [[ "$cars" =~ ^[0-9]+$ ]] || cars=1
  [[ "$PORT" =~ ^[0-9]+$ ]] || PORT=30814

  cat >"$cfg" <<EOF
# BeamMP server settings - created by BeamMP EasyServer
# Change anything here, then run:  sudo beammp restart
# The AuthKey is NOT stored here: it is kept encrypted (sudo beammp key).

[General]
Name = "$(toml_escape "$name")"
Port = $PORT
AuthKey = "" # stored encrypted - change with: sudo beammp key
AllowGuests = true
LogChat = true
Debug = false
IP = "::"
Private = $private
InformationPacket = true
Map = "/levels/$(toml_escape "$map")/info.json"
Description = "Hosted with BeamMP EasyServer"
MaxCars = $cars
MaxPlayers = $players
ResourceFolder = "Resources"
Tags = "Freeroam"

[Misc]
ImScaredOfUpdates = false
UpdateReminderTime = "30s"
EOF
  chown -h "$SERVICE_USER:$SERVICE_USER" "$cfg"
  [[ -L "$cfg" ]] || chmod 640 "$cfg"
  if [[ -z "$key" ]] && ! "$ES_DIR/secrets.sh" has BEAMMP_AUTH_KEY; then
    warn "No AuthKey yet. Add it later with:  sudo beammp key"
  fi
  ok "Settings saved to $cfg"
}

# ---- machine prep ------------------------------------------------------------
has_battery() { compgen -G "/sys/class/power_supply/BAT*" >/dev/null; }

prep_machine() {
  step "Preparing this computer to work as a server"

  # Firewall
  local ufw_state=""
  command -v ufw >/dev/null && ufw_state=$(ufw status 2>/dev/null || true)
  if [[ "$ufw_state" == *"Status: active"* ]]; then
    ufw allow "$PORT"/tcp >/dev/null && ufw allow "$PORT"/udp >/dev/null
    ok "Opened port $PORT in the firewall (ufw)"
  elif command -v firewall-cmd >/dev/null && firewall-cmd --state >/dev/null 2>&1; then
    firewall-cmd --permanent --add-port="$PORT"/tcp >/dev/null
    firewall-cmd --permanent --add-port="$PORT"/udp >/dev/null
    firewall-cmd --reload >/dev/null
    ok "Opened port $PORT in the firewall (firewalld)"
  else
    ok "No active firewall found - nothing to open"
  fi

  # Laptop: keep running with lid closed, never sleep
  local laptop="$OPT_LAPTOP"
  if [[ -z "$laptop" ]]; then
    if has_battery; then
      if ask_yn "This is a laptop. Keep the server running with the lid closed and never sleep?" Y; then
        laptop="yes"; else laptop="no"; fi
    else
      if ask_yn "Stop this computer from going to sleep (recommended for servers)?" Y; then
        laptop="yes"; else laptop="no"; fi
    fi
  fi
  if [[ "$laptop" == "yes" ]]; then
    mkdir -p "$(dirname "$LOGIND_DROPIN")"
    cat >"$LOGIND_DROPIN" <<'EOF'
# Added by BeamMP EasyServer - removed again by "beammp uninstall"
[Login]
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
HandleLidSwitchDocked=ignore
IdleAction=ignore
EOF
    systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target >/dev/null 2>&1 || true
    systemctl kill -s HUP systemd-logind >/dev/null 2>&1 || true
    ok "Sleep disabled, closing the lid won't stop the server"
  fi
}

# ---- service + helper --------------------------------------------------------
install_service() {
  step "Setting up auto-start"
  cat >"/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=BeamMP Server (BeamMP EasyServer)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$INSTALL_DIR
# launch.sh decrypts the AuthKey into memory, checks the mods for viruses,
# then runs the server as the unprivileged "beammp" user
ExecStart=$ES_DIR/launch.sh server
Restart=on-failure
RestartSec=5
StandardInput=null
NoNewPrivileges=true
TimeoutStartSec=infinity

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable "$SERVICE_NAME" >/dev/null 2>&1
  ok "Server will start automatically when the computer boots"

  # remember what we installed (used by "beammp update")
  cat >"$SECRETS_KEY_DIR/install.env" <<EOF
ASSET=$ASSET
EASY_VERSION=$EASY_VERSION
EOF

  cat >"$HELPER" <<'HELPER_EOF'
#!/usr/bin/env bash
# "beammp" - control command installed by BeamMP EasyServer
set -euo pipefail
DIR="/opt/beammp-server"; SVC="beammp-server"
RELEASE_BASE="https://github.com/BeamMP/BeamMP-Server/releases/latest/download"
need_root() { [[ $EUID -eq 0 ]] || exec sudo "$0" "$@"; }
# files in $DIR belong to the game server: root never writes them directly
AS_SERVER=(setpriv --reuid=beammp --regid=beammp --init-groups --)
AS_DASH=(setpriv --reuid=beammp-dash --regid=beammp-dash --init-groups --)
case "${1:-help}" in
  start)   need_root "$@"; systemctl start "$SVC"; echo "Started.";;
  stop)    need_root "$@"; systemctl stop "$SVC"; echo "Stopped.";;
  restart) need_root "$@"; systemctl restart "$SVC"; echo "Restarted.";;
  status)  systemctl status "$SVC" --no-pager || true;;
  logs)    need_root "$@"; journalctl -u "$SVC" -f -n 100;;
  config)  need_root "$@"; "${AS_SERVER[@]}" env HOME=/tmp "${EDITOR:-nano}" "$DIR/ServerConfig.toml"
           systemctl restart "$SVC"; echo "Saved and restarted.";;
  mods)    echo "Installed mods:"
           found=0
           for f in "$DIR"/Resources/Client/*.zip; do [[ -e "$f" ]] && { echo "  + $(basename "$f")"; found=1; }; done
           for f in "$DIR"/Resources/Client-disabled/*.zip; do [[ -e "$f" ]] && { echo "  - $(basename "$f")  (turned off)"; found=1; }; done
           [[ $found == 1 ]] || echo "  (none yet)"
           echo
           echo "Add mods:"
           if systemctl is-active --quiet beammp-dashboard; then
             conf=/etc/beammp-easyserver/modmanager.conf
             p=$(sed -n 's/^port *= *//p' "$conf"); pw=$(sudo /usr/local/lib/beammp-easyserver/secrets.sh get MODS_PASSWORD)
             echo "  Dashboard: http://$(hostname -I | awk '{print $1}'):${p:-30815}   password: $pw"
           fi
           echo "  Folder:    ~/BeamMP-Mods   ($DIR/Resources/Client)"
           echo "  Command:   beammp addmod file1.zip file2.zip ..."
           echo "  Server plugins (Lua) go in: $DIR/Resources/Server"
           echo "The server restarts by itself ~15 s after mods change.";;
  addmod)  shift || true
           [[ $# -gt 0 ]] || { echo "Usage: beammp addmod file.zip [more.zip ...]"; exit 1; }
           [[ $EUID -eq 0 ]] || exec sudo "$0" addmod "$@"
           up="$DIR/Resources/.uploading"
           [[ -L "$up" ]] && rm -f "$up"
           "${AS_SERVER[@]}" mkdir -p "$up"; "${AS_SERVER[@]}" chmod 2775 "$up"
           for f in "$@"; do
             if [[ "$f" != *.zip && "$f" != *.ZIP ]]; then echo "Skipped (not a .zip): $f"; continue; fi
             [[ -f "$f" ]] || { echo "Not found: $f"; continue; }
             tmp="$up/$(basename "$f")"
             # written by the dashboard user (not root) so links in the folder can't redirect it
             "${AS_DASH[@]}" sh -c 'umask 002; rm -f "$1"; cat > "$1"' sh "$tmp" < "$f"
             echo "Checking $(basename "$f") for viruses..."
             vt=$(/usr/local/lib/beammp-easyserver/secrets.sh get VT_API_KEY 2>/dev/null || true)
             if ! VT_API_KEY="$vt" MODSCAN_CACHE="$DIR/.easyserver/scancache.json" HOME="$DIR" setpriv --reuid=beammp-dash --regid=beammp-dash --init-groups -- \
                  python3 /usr/local/lib/beammp-easyserver/dashboard/modscan.py "$tmp"; then
               rm -f "$tmp"; echo "NOT added: $(basename "$f") failed the safety check."; continue
             fi
             unset vt
             "${AS_DASH[@]}" mv -f "$tmp" "$DIR/Resources/Client/$(basename "$f")"
             echo "Added: $(basename "$f")"
             maps=$(python3 - "$f" <<'PYEOF' 2>/dev/null || true
import re,sys,zipfile
print(" ".join(sorted({m.group(1) for n in zipfile.ZipFile(sys.argv[1]).namelist() for m in [re.match(r"^levels/([^/]+)/info\.json$",n,re.I)] if m})))
PYEOF
)
             [[ -n "$maps" ]] && echo "  This mod contains a map: $maps   -> use it with: beammp map ${maps%% *}"
           done
           echo "The server restarts by itself in ~15 seconds.";;
  map)     shift || true
           [[ -n "${1:-}" ]] || { echo "Current: $(sudo grep -E '^\s*Map' "$DIR/ServerConfig.toml")"; echo "Usage: beammp map west_coast_usa"; exit 0; }
           need_root map "$@"
           [[ "$1" =~ ^[A-Za-z0-9_.-]+$ ]] || { echo "Invalid map name"; exit 1; }
           "${AS_SERVER[@]}" sed -i -E "s|^\s*Map\s*=.*|Map = \"/levels/$1/info.json\"|" "$DIR/ServerConfig.toml"
           "${AS_SERVER[@]}" touch "$DIR/Resources/Client"
           echo "Map set to $1 - the server restarts by itself in ~15 seconds.";;
  update)  need_root "$@"
           # shellcheck disable=SC1091
           . /etc/beammp-easyserver/install.env
           tmp=$(mktemp)
           echo "Downloading newest $ASSET ..."
           curl -fL --retry 3 --progress-bar -o "$tmp" "$RELEASE_BASE/$ASSET"
           head -c 4 "$tmp" | grep -q ELF || { rm -f "$tmp"; echo "Download was not a Linux program."; exit 1; }
           systemctl stop "$SVC"
           chmod 644 "$tmp"
           "${AS_SERVER[@]}" sh -c 'umask 022; t=$(mktemp "$1/.update-XXXXXX") && cat > "$t" && chmod 755 "$t" && mv -f "$t" "$1/BeamMP-Server"' sh "$DIR" < "$tmp"
           rm -f "$tmp"
           systemctl start "$SVC"; echo "Updated and restarted.";;
  key)     need_root "$@"
           echo "Get a key at https://keymaster.beammp.com (Keys -> +)."
           read -r -s -p "Paste your BeamMP AuthKey (hidden, Enter = keep current): " k </dev/tty; echo
           k="${k//[[:space:]]/}"
           [[ -n "$k" ]] || { echo "Unchanged."; exit 0; }
           [[ "$k" =~ ^[A-Za-z0-9-]+$ ]] || { echo "That doesn't look like an AuthKey."; exit 1; }
           printf '%s\n' "$k" | /usr/local/lib/beammp-easyserver/secrets.sh set BEAMMP_AUTH_KEY
           systemctl restart "$SVC"; echo "AuthKey saved encrypted (****${k: -4}) and server restarted.";;
  virustotal) need_root "$@"
           echo "Free key: make an account at https://www.virustotal.com/gui/join-us,"
           echo "then click your name (top right) -> API key."
           read -r -s -p "Paste your VirusTotal API key (hidden, 'off' = remove): " k </dev/tty; echo
           k="${k//[[:space:]]/}"
           if [[ "$k" == "off" ]]; then /usr/local/lib/beammp-easyserver/secrets.sh unset VT_API_KEY; echo "VirusTotal check turned off."
           elif [[ "$k" =~ ^[a-f0-9]{64}$ ]]; then printf '%s\n' "$k" | /usr/local/lib/beammp-easyserver/secrets.sh set VT_API_KEY; echo "Saved encrypted (****${k: -4})."
           else echo "That doesn't look like a VirusTotal key (64 letters/numbers)."; exit 1; fi
           systemctl try-restart beammp-dashboard 2>/dev/null || true;;
  dashboard) conf=/etc/beammp-easyserver/modmanager.conf
           p=$(sed -n 's/^port *= *//p' "$conf" 2>/dev/null); proto=http
           if sudo grep -q '"https": true' "$DIR/.easyserver/dashboard.json" 2>/dev/null; then proto=https; fi
           echo "Dashboard: $proto://$(hostname -I | awk '{print $1}'):${p:-30815}"
           echo "Password:  $(sudo /usr/local/lib/beammp-easyserver/secrets.sh get MODS_PASSWORD)"
           systemctl is-active --quiet beammp-dashboard || echo "(the dashboard is not running - start it: sudo systemctl start beammp-dashboard)";;
  reset-login) need_root "$@"
           echo "This sets a new dashboard password, turns off two-step login and internet access."
           read -r -s -p "New dashboard password (min. 8 characters): " k </dev/tty; echo
           [[ ${#k} -ge 8 ]] || { echo "Too short."; exit 1; }
           printf '%s\n' "$k" | /usr/local/lib/beammp-easyserver/secrets.sh set MODS_PASSWORD
           /usr/local/lib/beammp-easyserver/secrets.sh unset TOTP_SECRET
           f="$DIR/.easyserver/dashboard.json"
           if [[ -f "$f" ]]; then
             "${AS_DASH[@]}" python3 - "$f" <<'PYEOF'
import json, sys
p = sys.argv[1]
d = json.load(open(p))
d["remote_enabled"] = False
json.dump(d, open(p, "w"), indent=1)
PYEOF
           fi
           systemctl restart beammp-dashboard
           echo "Done. Log in with the new password.";;
  scan)    need_root "$@"
           vt=$(/usr/local/lib/beammp-easyserver/secrets.sh get VT_API_KEY 2>/dev/null || true)
           shift || true
           targets=("$@"); [[ ${#targets[@]} -gt 0 ]] || targets=("$DIR"/Resources/Client/*.zip)
           [[ -e "${targets[0]}" ]] || { echo "No mods to check."; exit 0; }
           VT_API_KEY="$vt" MODSCAN_CACHE="$DIR/.easyserver/scancache.json" HOME="$DIR" setpriv --reuid=beammp-dash --regid=beammp-dash --init-groups -- \
             python3 /usr/local/lib/beammp-easyserver/dashboard/modscan.py "${targets[@]}" || true
           echo; echo "Blocked mods are kept in $DIR/Resources/Quarantine";;
  ip)      echo "LAN address:    $(hostname -I | awk '{print $1}')"
           echo "Public address: $(curl -fsS --max-time 5 https://api.ipify.org || echo unknown)";;
  uninstall) need_root "$@"
           systemctl disable --now "$SVC" 2>/dev/null || true
           systemctl disable --now beammp-mods beammp-dashboard beammp-mods-apply.path beammp-control.path 2>/dev/null || true
           for d in "$DIR"/servers/*/; do      # extra servers made in the dashboard
             [[ -d "$d" ]] || continue; id=$(basename "$d")
             systemctl disable --now "beammp-server@$id" "beammp-mods-apply@$id.path" 2>/dev/null || true
           done
           rm -rf /etc/beammp-easyserver/limits /etc/systemd/system.control/beammp-server*.service.d
           python3 /usr/local/lib/beammp-easyserver/control.py --shape >/dev/null 2>&1 || true   # removes the upload limits
           nft delete table inet beammp_easyserver 2>/dev/null || true                           # flood protection rules
           rm -f "/etc/systemd/system/$SVC.service" /etc/systemd/system/beammp-mods.service \
                 /etc/systemd/system/beammp-dashboard.service /etc/systemd/system/beammp-control.service \
                 /etc/systemd/system/beammp-control.path \
                 /etc/systemd/system/beammp-mods-apply.service /etc/systemd/system/beammp-mods-apply.path \
                 /etc/systemd/system/beammp-server@.service /etc/systemd/system/beammp-mods-apply@.service \
                 /etc/systemd/system/beammp-mods-apply@.path
           systemctl daemon-reload
           for h in /home/*/BeamMP-Mods /home/*/*/BeamMP-Mods; do [[ -L "$h" ]] && rm -f "$h"; done
           if [[ -f /etc/systemd/logind.conf.d/99-beammp-easyserver.conf ]]; then
             rm -f /etc/systemd/logind.conf.d/99-beammp-easyserver.conf
             systemctl unmask sleep.target suspend.target hibernate.target hybrid-sleep.target 2>/dev/null || true
             systemctl kill -s HUP systemd-logind 2>/dev/null || true
           fi
           read -r -p "Also delete the server folder with your config and mods ($DIR)? (y/N): " a </dev/tty || a=n
           if [[ "$a" =~ ^[Yy] ]]; then rm -rf "$DIR"; userdel beammp-dash 2>/dev/null || true; userdel beammp 2>/dev/null || true; fi
           rm -rf /usr/local/lib/beammp-easyserver
           if [[ ! -d "$DIR" ]]; then rm -rf /etc/beammp-easyserver /var/lib/beammp-easyserver
           else echo "Your encrypted keys are kept in /var/lib/beammp-easyserver (delete it to remove them)."; fi
           rm -f /usr/local/bin/beammp
           echo "BeamMP EasyServer removed.";;
  *) cat <<EOF
BeamMP EasyServer - commands:
  beammp status     is it running?
  beammp logs       live server console (Ctrl+C to leave)
  beammp start | stop | restart
  beammp config     edit settings (name, map, key...) and restart
  beammp mods       list mods + how to add them (web page password)
  beammp addmod F   add mod .zip file(s)
  beammp map NAME   change the map (e.g. beammp map italy)
  beammp scan       virus-check all mods again
  beammp key        change your BeamMP AuthKey (stored encrypted)
  beammp virustotal set/remove the VirusTotal key (stored encrypted)
  beammp dashboard  dashboard address and password
  beammp reset-login  new dashboard password, turns off two-step login (lost phone)
  beammp ip         addresses your friends connect to
  beammp update     download the newest BeamMP server
  beammp uninstall  remove everything
EOF
  ;;
esac
HELPER_EOF
  chmod 0755 "$HELPER"
  ok "Installed the 'beammp' command"
}

# ---- dashboard, easy mods, auto-apply ----------------------------------------
desktop_user() { # the normal user who ran sudo
  local u="${SUDO_USER:-}"
  [[ -z "$u" && -n "${PKEXEC_UID:-}" ]] && u=$(id -nu "$PKEXEC_UID" 2>/dev/null || true)
  [[ "$u" == "root" ]] && u=""
  echo "$u"
}

install_mods() {
  step "Setting up the dashboard and easy mod uploading"
  local es="$ES_DIR"
  mkdir -p "$INSTALL_DIR/Resources/Client-disabled" "$INSTALL_DIR/Resources/Quarantine" \
           "$INSTALL_DIR/Resources/Server/EasyServerStats" "$es/dashboard"

  # Mods folder: group-writable so your own user can drop files in it
  chgrp "$SERVICE_USER" "$INSTALL_DIR/Resources/Client" "$INSTALL_DIR/Resources/Client-disabled"
  chmod 2775 "$INSTALL_DIR/Resources/Client" "$INSTALL_DIR/Resources/Client-disabled"
  local du; du=$(desktop_user)
  if [[ -n "$du" ]]; then
    usermod -aG "$SERVICE_USER" "$du" || true
    local home; home=$(getent passwd "$du" | cut -d: -f6)
    if [[ -n "$home" && -d "$home" ]]; then
      ln -sfn "$INSTALL_DIR/Resources/Client" "$home/BeamMP-Mods"
      chown -h "$du:" "$home/BeamMP-Mods" 2>/dev/null || true
      local desk=""
      command -v xdg-user-dir >/dev/null && desk=$(sudo -u "$du" xdg-user-dir DESKTOP 2>/dev/null || true)
      if [[ -n "$desk" && -d "$desk" && "$desk" != "$home" ]]; then
        ln -sfn "$INSTALL_DIR/Resources/Client" "$desk/BeamMP-Mods"
        chown -h "$du:" "$desk/BeamMP-Mods" 2>/dev/null || true
      fi
      ok "Mods folder linked at ~/BeamMP-Mods (works after you log out and back in)"
    fi
  fi

  # Auto-apply: restart the server ~15 s after the mods (or map) change
  cat >"$es/apply.sh" <<'APPLY_EOF'
#!/usr/bin/env bash
# Restarts the BeamMP server when mods or settings really changed.
# "apply.sh --record" only saves the current state (used by the installer).
# "apply.sh [--record] [<id>]": <id> = extra server in /opt/beammp-server/servers/<id>
REC=""; [[ "${1:-}" == "--record" ]] && { REC=1; shift; }
ID="${1:-main}"
[[ -n "$REC" ]] || sleep 15
DIR=/opt/beammp-server; UNIT=beammp-server; STATE=/var/lib/beammp-easyserver/applied
if [[ "$ID" != "main" ]]; then
  [[ "$ID" =~ ^[a-z0-9]{1,12}$ && -d "$DIR/servers/$ID" && ! -L "$DIR/servers/$ID" ]] || exit 0
  DIR="$DIR/servers/$ID"; UNIT="beammp-server@$ID"; STATE="$STATE-$ID"
fi
if [[ -z "$REC" ]]; then
  # virus-check new mods first; bad ones go to Resources/Quarantine
  VT=$(/usr/local/lib/beammp-easyserver/secrets.sh get VT_API_KEY 2>/dev/null || true)
  [[ -n "$VT" ]] && export VT_API_KEY="$VT"
  export MODSCAN_CACHE=/opt/beammp-server/.easyserver/scancache.json HOME=$DIR
  setpriv --reuid=beammp-dash --regid=beammp-dash --init-groups -- \
    python3 /usr/local/lib/beammp-easyserver/dashboard/modscan.py --sweep "$DIR/Resources/Client" "$DIR/Resources/Quarantine" || true
  unset VT_API_KEY VT
fi
# only the mod zips and the config count (the server writes its own mods.json)
# (read as the dashboard user, never as root: these folders belong to the server)
NOW=$(setpriv --reuid=beammp-dash --regid=beammp-dash --init-groups -- timeout 20 sh -c \
  'ls -l --time-style=+%s "$1"/Resources/Client/*.zip 2>/dev/null; head -c 262144 "$1/ServerConfig.toml" 2>/dev/null' sh "$DIR" \
  | md5sum | cut -d' ' -f1)
[[ -n "$REC" ]] && { echo "$NOW" > "$STATE"; exit 0; }
[[ -f "$STATE" && "$(cat "$STATE")" == "$NOW" ]] && exit 0
echo "$NOW" > "$STATE"
systemctl try-restart "$UNIT"
echo "Mods/map changed - server restarted"
APPLY_EOF
  chmod 0755 "$es/apply.sh"
  cat >/etc/systemd/system/beammp-mods-apply.service <<EOF
[Unit]
Description=Apply BeamMP mod changes (BeamMP EasyServer)
[Service]
Type=oneshot
ExecStart=$es/apply.sh
EOF
  cat >/etc/systemd/system/beammp-mods-apply.path <<EOF
[Unit]
Description=Watch BeamMP mods folder (BeamMP EasyServer)
[Path]
PathChanged=$INSTALL_DIR/Resources/Client
PathChanged=$INSTALL_DIR/ServerConfig.toml
[Install]
WantedBy=multi-user.target
EOF
  # extra servers (created from the dashboard): beammp-server@<id> + its mod watcher
  mkdir -p "$INSTALL_DIR/servers" /etc/beammp-easyserver/limits
  chown root:root "$INSTALL_DIR/servers"; chmod 755 "$INSTALL_DIR/servers"
  cat >/etc/systemd/system/beammp-server@.service <<EOF
[Unit]
Description=BeamMP Server %i (BeamMP EasyServer)
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
WorkingDirectory=$INSTALL_DIR/servers/%i
ExecStart=$es/launch.sh server %i
Restart=on-failure
RestartSec=5
StandardInput=null
NoNewPrivileges=true
TimeoutStartSec=infinity
[Install]
WantedBy=multi-user.target
EOF
  cat >/etc/systemd/system/beammp-mods-apply@.service <<EOF
[Unit]
Description=Apply BeamMP mod changes for server %i (BeamMP EasyServer)
[Service]
Type=oneshot
ExecStart=$es/apply.sh %i
EOF
  cat >/etc/systemd/system/beammp-mods-apply@.path <<EOF
[Unit]
Description=Watch BeamMP mods folder of server %i (BeamMP EasyServer)
[Path]
PathChanged=$INSTALL_DIR/servers/%i/Resources/Client
PathChanged=$INSTALL_DIR/servers/%i/ServerConfig.toml
[Install]
WantedBy=multi-user.target
EOF

  # Web dashboard
  local page="$OPT_MODPAGE"
  if [[ -z "$page" ]]; then
    echo "  The dashboard lets you manage the server and drag & drop mods from any PC or phone."
    if ask_yn "Turn on the web dashboard?" Y; then page="yes"; else page="no"; fi
  fi

  local f
  for f in dashboard.py webui.html modscan.py tlsgen.py; do
    fetch_file "dashboard/$f" "$es/dashboard/$f"
  done
  fetch_file "linux/control.py" "$es/control.py"
  rm -f "$es/modmanager.py" "$es/modscan.py"
  # player statistics plugin (runs inside the BeamMP server)
  fetch_file "dashboard/EasyServerStats/main.lua" "$INSTALL_DIR/Resources/Server/EasyServerStats/main.lua"
  chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR/Resources/Server/EasyServerStats"
  chmod 2775 "$INSTALL_DIR/Resources/Server/EasyServerStats"
  # extra servers made in the dashboard get the same plugin. Written as the game
  # server user from a private copy, so a planted link can't make root read or
  # write anything else.
  local luatmp sd; luatmp=$(mktemp)
  fetch_file "dashboard/EasyServerStats/main.lua" "$luatmp"
  for sd in "$INSTALL_DIR"/servers/*/; do
    [[ -d "$sd" && ! -L "${sd%/}" ]] || continue
    setpriv --reuid="$SERVICE_USER" --regid="$SERVICE_USER" --init-groups -- \
      sh -c 'mkdir -p "$1" && cat > "$1/main.lua.tmp" && mv -f "$1/main.lua.tmp" "$1/main.lua"' _ \
      "${sd}Resources/Server/EasyServerStats" < "$luatmp" || warn "Couldn't update the plugin in $sd"
  done
  rm -f "$luatmp"

  local conf="$SECRETS_KEY_DIR/modmanager.conf"
  [[ -f "$conf" ]] || printf 'port = %s\nuser = admin\n' "$MODS_PORT" >"$conf"
  # old versions kept the password in plain text: move it to encrypted storage
  local oldpw; oldpw=$(sed -n 's/^password *= *//p' "$conf")
  if [[ -n "$oldpw" ]]; then secret_set MODS_PASSWORD "$oldpw"; sed -i '/^password *=/d' "$conf"; fi
  if ! "$ES_DIR/secrets.sh" has MODS_PASSWORD; then
    secret_set MODS_PASSWORD "$(python3 -c 'import secrets,string;print("".join(secrets.choice(string.ascii_lowercase+string.digits) for _ in range(10)))')"
  fi
  MODS_PORT=$(sed -n 's/^port *= *//p' "$conf"); MODS_PORT=${MODS_PORT:-30815}
  MODS_PASS=$("$ES_DIR/secrets.sh" get MODS_PASSWORD)
  chown "$DASH_USER:$SERVICE_USER" "$INSTALL_DIR/Resources/Quarantine"
  chmod 2775 "$INSTALL_DIR/Resources/Quarantine"
  chown -R "$DASH_USER:$DASH_USER" "$DATA_DIR"; chmod 750 "$DATA_DIR"
  [[ -f "$INSTALL_DIR/ServerConfig.toml" && ! -L "$INSTALL_DIR/ServerConfig.toml" ]] && chmod 660 "$INSTALL_DIR/ServerConfig.toml"
  chown -R root:root "$es"
  chmod 755 "$es/dashboard"; chmod 644 "$es/dashboard"/*
  chmod 755 "$es/apply.sh"; chmod 700 "$es/secrets.sh" "$es/launch.sh" "$es/control.py"
  chmod 644 "$conf"

  # Virus check: VirusTotal (optional, free account)
  local vt="$OPT_VTKEY"
  if [[ -z "$vt" ]] && ! "$es/secrets.sh" has VT_API_KEY && [[ $OPT_UNATTENDED -eq 0 ]]; then
    echo
    echo "  ${C_BOLD}Mod virus check${C_RESET}: every mod is checked before players get it (built in, always on)."
    echo "  For extra safety it can also ask VirusTotal (70+ antivirus programs). Free:"
    echo "    1) Make an account at https://www.virustotal.com/gui/join-us"
    echo "    2) Click your name (top right) -> API key -> copy it"
    vt=$(ask_secret "Paste your VirusTotal API key (or press Enter to skip)")
  fi
  vt="${vt//[[:space:]]/}"
  if [[ -n "$vt" ]]; then
    if [[ "$vt" =~ ^[a-f0-9]{64}$ ]]; then
      secret_set VT_API_KEY "$vt"; ok "VirusTotal key saved encrypted ($(mask "$vt"))"
    else
      warn "That doesn't look like a VirusTotal key (64 letters/numbers) - skipped. Add it later: sudo beammp virustotal"
    fi
  fi

  # older versions had a separate mod page service
  if [[ -f /etc/systemd/system/beammp-mods.service ]]; then
    systemctl disable --now beammp-mods >/dev/null 2>&1 || true
    rm -f /etc/systemd/system/beammp-mods.service
  fi
  cat >/etc/systemd/system/beammp-dashboard.service <<EOF
[Unit]
Description=BeamMP dashboard (BeamMP EasyServer)
After=network-online.target
Wants=network-online.target
[Service]
ExecStart=$ES_DIR/launch.sh dashboard
Restart=on-failure
RestartSec=5
[Install]
WantedBy=multi-user.target
EOF
  # root helper: does only a fixed list of jobs the dashboard asks for
  cat >/etc/systemd/system/beammp-control.service <<EOF
[Unit]
Description=BeamMP dashboard helper (BeamMP EasyServer)
[Service]
Type=oneshot
ExecStart=/usr/bin/env python3 $ES_DIR/control.py
EOF
  cat >/etc/systemd/system/beammp-control.path <<EOF
[Unit]
Description=Watch for BeamMP dashboard requests (BeamMP EasyServer)
[Path]
PathExistsGlob=/run/beammp-easyserver-ctl/*.req
[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable --now beammp-control.path >/dev/null 2>&1
  "$es/apply.sh" --record || true
  systemctl enable --now beammp-mods-apply.path >/dev/null 2>&1
  ok "Server restarts automatically ~15 seconds after mods change"

  if [[ "$page" == "yes" ]]; then
    systemctl enable beammp-dashboard >/dev/null 2>&1
    systemctl restart beammp-dashboard
    # open the port for the home network only (never forward this one!)
    local ufw_state=""
    command -v ufw >/dev/null && ufw_state=$(ufw status 2>/dev/null || true)
    if [[ "$ufw_state" == *"Status: active"* ]]; then
      for net in 192.168.0.0/16 10.0.0.0/8 172.16.0.0/12; do
        ufw allow from "$net" to any port "$MODS_PORT" proto tcp >/dev/null
      done
    elif command -v firewall-cmd >/dev/null && firewall-cmd --state >/dev/null 2>&1; then
      firewall-cmd --permanent --add-port="$MODS_PORT"/tcp >/dev/null; firewall-cmd --reload >/dev/null
    fi
    MODPAGE_ON=1
    ok "Dashboard is on (port $MODS_PORT, home network only unless you allow more)"
  else
    systemctl disable --now beammp-dashboard >/dev/null 2>&1 || true
    MODPAGE_ON=0
  fi
}

# ---- uninstall / update shortcuts -------------------------------------------
if [[ "$MODE" == "uninstall" ]]; then
  [[ -x "$HELPER" ]] || die "BeamMP EasyServer is not installed."
  exec "$HELPER" uninstall
fi
if [[ "$MODE" == "update" ]]; then
  [[ -x "$HELPER" ]] || die "BeamMP EasyServer is not installed yet - run without --update first."
  exec "$HELPER" update
fi

# ---- main install ------------------------------------------------------------
clear 2>/dev/null || true
echo "${C_BOLD}"
echo "  ========================================="
echo "     BeamMP EasyServer v$EASY_VERSION - Linux"
echo "     One-click BeamMP server installer"
echo "  ========================================="
echo "${C_RESET}"

detect_system
echo "  System:  $OS_PRETTY ($ARCH)"
echo "  Server build:  $ASSET"
[[ "$SUPPORT" == "best-effort" ]] && warn "Your distro has no official BeamMP build - trying the Ubuntu 24.04 build (usually works)."

install_deps

step "Creating the server user and folder"
id "$SERVICE_USER" >/dev/null 2>&1 || \
  useradd --system --home-dir "$INSTALL_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
# separate user for the dashboard, so the game server can't control it
id "$DASH_USER" >/dev/null 2>&1 || \
  useradd --system --user-group --no-create-home --home-dir "$INSTALL_DIR/.easyserver" \
          --shell /usr/sbin/nologin "$DASH_USER"
usermod -aG "$SERVICE_USER" "$DASH_USER"
# Stop everything that runs as the server users while root works in their
# folder, and remove links they could have planted (so a hacked game server
# can't trick the installer into writing or chown-ing system files).
EXTRA_ACTIVE=$(systemctl list-units --plain --no-legend --state=active 'beammp-server@*.service' 2>/dev/null | awk '{print $1}' || true)
systemctl stop "$SERVICE_NAME" beammp-dashboard 'beammp-server@*.service' 2>/dev/null || true
drop_links
mkdir -p "$INSTALL_DIR/Resources/Client" "$INSTALL_DIR/Resources/Server"
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
ok "$INSTALL_DIR"

download_server
fix_lua_link
setup_secrets
configure
prep_machine
install_service
MODPAGE_ON=0
install_mods

step "Starting the server"
systemctl restart "$SERVICE_NAME"
for u in $EXTRA_ACTIVE; do systemctl start "$u" 2>/dev/null || true; done
sleep 4
if systemctl is-active --quiet "$SERVICE_NAME"; then
  ok "Server is running!"
else
  warn "The server didn't stay running. Last log lines:"
  journalctl -u "$SERVICE_NAME" -n 15 --no-pager | sed 's/^/      /' || true
fi

LAN_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
PUB_IP=$(curl -fsS --max-time 5 https://api.ipify.org 2>/dev/null || echo "unknown")

cat <<EOF

${C_GREEN}${C_BOLD}  All done!${C_RESET}

  Friends on the same Wi-Fi/network connect to:  ${C_BOLD}${LAN_IP:-?}:${PORT}${C_RESET}
  Friends over the internet connect to:          ${C_BOLD}${PUB_IP}:${PORT}${C_RESET}
    -> for internet play, forward port ${PORT} (TCP + UDP) on your router
       to ${LAN_IP:-this computer}. Search "<your router model> port forwarding".

${C_BOLD}  Dashboard (manage everything from any PC or phone):${C_RESET}
EOF
if [[ "$MODPAGE_ON" == 1 ]]; then
cat <<EOF
    Open:      ${C_BOLD}http://${LAN_IP:-this-computer}:${MODS_PORT}${C_RESET}
    Password:  ${C_BOLD}${MODS_PASS}${C_RESET}   (see it again: beammp dashboard)
    Config editor, mods, player stats, network check, updates, notifications...
EOF
fi
cat <<EOF

${C_BOLD}  Adding mods:${C_RESET}
    Drag & drop them onto the dashboard's Mods page
    On this computer: drop .zip files into the ${C_BOLD}BeamMP-Mods${C_RESET} folder in your home folder
    Or: beammp addmod ~/Downloads/some_mod.zip
    The server restarts by itself ~15 seconds after mods change.
    Every mod is virus-checked first; bad ones go to Resources/Quarantine.
    Your keys are stored encrypted (change: sudo beammp key / sudo beammp virustotal).

  Useful commands:
    beammp status    beammp logs    beammp config    beammp mods
    beammp update    beammp ip      beammp uninstall

EOF
pause_if_terminal
