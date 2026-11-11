# BeamMP EasyServer

**Host your own BeamNG.drive multiplayer (BeamMP) server in one click, on Windows or Linux.**

No config files, no command line knowledge needed. The installer downloads the newest official BeamMP server, asks a few simple questions (name, map, player count), sets everything up and starts it. Then you manage everything from a **web dashboard** on any PC or phone.

> Not affiliated with or endorsed by the BeamMP team. This only automates the setup of the official [BeamMP server](https://github.com/BeamMP/BeamMP-Server).

---

## 🖥️ The dashboard

Open `http://<server-ip>:30815` from any PC or phone at home, or use the **BeamMP Dashboard** shortcut on Windows.

| Page | What you can do |
|---|---|
| **Overview** | Server status, who's online, uptime, start / stop / restart |
| **Config** | Edit every server setting in a simple form, or as text, **without touching files**. Every change is checked first (wrong types, bad ports, unknown maps, duplicate lines…) and you get plain-English errors with line numbers |
| **Mods** | Drag & drop mods, turn them on/off, pick map mods, see the virus check result for each |
| **Players** | Player analytics: players per day, busiest hours, a week heatmap, top players, sessions, peak and usage |
| **Network** | Port checker: is the server listening, reachable at home, reachable from the internet, listed in the BeamMP server list? Tells you what to fix |
| **Updates** | Checks for new BeamMP server and EasyServer versions, installs server updates in one click |
| **Logs** | Live server log, with hints that explain common errors in plain English |
| **Notifications** | Crashes, unexpected stops, updates, blocked mods, failed logins, player joins. Shown in the dashboard and optionally sent to **Discord** and/or **email** |
| **Settings** | Notifications, password, **two-step login**, **access from the internet (HTTPS)**, **backup / import / export** |

Also: **dark / light mode** (follows your system, or switch with the moon icon), and it works on phones.

### Access from the internet (optional, off by default)

To manage the server when you're not at home, go to **Settings → Access from the internet**. It's only allowed when all of these are true:
- **HTTPS** is on. The dashboard makes its own certificate, so your browser warns you the first time; compare the fingerprint shown in Settings, then continue.
- **Two-step login** is on, with codes from Google Authenticator, Microsoft Authenticator, Aegis or similar.
- Your password has at least 12 characters.

Then forward port **30815 (TCP)** on your router. Wrong passwords lock out the visitor for 15 minutes, and you get a notification.

Forgot the password or lost your phone? On Linux run `sudo beammp reset-login`. On Windows double-click `Reset-Dashboard-Login.bat`, then open the dashboard on the server PC to set a new password.

### Backup and moving servers

**Settings → Backup** exports your config and settings (optionally all mods) into one file. Import it on another EasyServer and the mods are virus-checked again on the way in. Keys and passwords are never exported.

---

## Before you start: get your free AuthKey (1 minute)

1. Go to **https://keymaster.beammp.com** and log in with Discord
2. Click **Keys**, then **+**, give it any name
3. Copy the key; the installer will ask for it

---

## Windows

1. Download **BeamMP-EasyServer-Windows.zip** from the [Releases page](https://github.com/scheidlerbalint1103-dev/beammp-easyserver/releases/latest) and extract it (or use the green **Code** button → **Download ZIP** and open the `windows` folder)
2. Double-click **`Install-BeamMP-Server.bat`**
3. Click **Yes** when Windows asks for permission
4. Fill in the window (paste your AuthKey) and press **Install**

That's it. You get a **Start BeamMP Server** shortcut on your desktop.

It also handles:
- The **web dashboard** (a small portable Python is downloaded for it; it starts when you log in). The first time you open it, you create a password
- A **Drop BeamMP Mods Here** desktop icon: drag mod zips onto it (each one is virus-checked first)
- Your AuthKey and VirusTotal key are stored **encrypted**
- Microsoft Visual C++ Runtime (installed automatically if missing)
- Windows Firewall rules for the server port
- Optional auto-start when you log in

| File | What it does |
|---|---|
| `Install-BeamMP-Server.bat` | Install, or change settings later (run it again) |
| `Add-Mods.bat` | Drag mod .zip files onto it (same as the desktop icon) |
| `Reset-Dashboard-Login.bat` | Forgot the dashboard password or lost your two-step phone |
| `Update-BeamMP-Server.bat` | Download the newest BeamMP server |
| `Uninstall-BeamMP-Server.bat` | Remove everything |

---

## Linux (recommended for a dedicated server)

Linux runs the server in the background as a service. It starts by itself when the computer boots, and it runs well on old laptops and PCs.

### Option A: one command

Open a terminal and paste:

```bash
curl -fsSL https://raw.githubusercontent.com/scheidlerbalint1103-dev/beammp-easyserver/main/linux/install.sh | sudo bash
```

### Option B: download and run

1. Download **BeamMP-EasyServer-Linux.zip** from the [Releases page](https://github.com/scheidlerbalint1103-dev/beammp-easyserver/releases/latest) and extract it
2. Double-click **`install.sh`** and choose **Run in Terminal**
   - Doesn't run? Right-click inside the folder → **Open in Terminal**, then type `bash install.sh` and press Enter
3. Enter your password and answer the questions

### What the Linux installer does automatically

- Detects your distro and downloads the matching official build
- Installs the needed libraries (Lua 5.3)
- Creates a separate `beammp` user so the server doesn't run as root
- Creates a **systemd service** so the server starts on boot and restarts if it crashes
- Opens the port in the firewall (ufw / firewalld) if one is active
- **Laptop mode:** keeps the server running with the lid closed and stops the machine from going to sleep
- Sets up **easy mod uploading**: a drag & drop web page, a `BeamMP-Mods` folder, and automatic restart when mods change
- **Virus-checks every mod** and **stores your keys encrypted** (see below)
- Installs the **web dashboard** (runs as its own limited user, separate from the game server)
- Installs a simple `beammp` command to manage it

### Managing the server

```
beammp status      is it running?
beammp logs        live server console (Ctrl+C to leave)
beammp restart     restart (also: start / stop)
beammp config      edit name, map, key... then auto-restart
beammp dashboard   dashboard address and password
beammp reset-login new dashboard password, turns off two-step login (lost phone)
beammp mods        list mods
beammp addmod F    add mod .zip file(s)
beammp map NAME    change the map (e.g. beammp map italy)
beammp scan        virus-check all mods again
beammp key         change your BeamMP AuthKey (stored encrypted)
beammp virustotal  set or remove the VirusTotal key (stored encrypted)
beammp ip          the addresses your friends connect to
beammp update      download the newest BeamMP server
beammp uninstall   remove everything (also undoes laptop mode)
```

### Supported systems

| Distro | Status |
|---|---|
| Ubuntu 22.04 / 24.04 and newer | ✅ official build |
| Linux Mint 21 / 22, Pop!_OS, Zorin, elementary | ✅ official build |
| Debian 12 / 13, LMDE 6+ | ✅ official build |
| Fedora, Arch, openSUSE | ⚠️ best effort |
| 64-bit x86 and ARM64 (e.g. Raspberry Pi 4/5 with 64-bit OS) | ✅ |

### Advanced (no questions asked)

```bash
sudo bash install.sh --unattended --key YOUR_KEY --name "My Server" \
  --map west_coast_usa --players 10 --public --laptop-mode yes --mod-page yes
```

Run `bash install.sh --help` for all options.

---

## Letting friends join over the internet

Friends on the **same Wi-Fi** can join right away using the LAN address shown at the end of the install.

For friends **anywhere else**, forward port **30814** (both **TCP and UDP**) on your router to the server computer. Search for "*your router model* port forwarding" for instructions. Then your server shows up in the BeamMP server list (if you chose public), or friends can connect with your public IP.

## 🛡️ Mod virus check

Every mod is checked **before** players can download it, whichever way you add it (web page, folder, drag & drop or command). Mods that fail are refused, or moved to `Resources/Quarantine` with a note explaining why.

| Check | Windows | Linux | What it catches |
|---|---|---|---|
| **Built-in checks** (always on, offline) | ✅ | ✅ | Hidden programs (`.exe`, `.dll`, `.bat`, `.ps1`...), files that are secretly programs (e.g. a "texture" that is really an `.exe`), disguised names like `photo.jpg.scr`, password-protected files, "zip bombs", and files trying to escape the mods folder |
| **Lua script check** | ✅ | ✅ | Warns about mod scripts that can run commands, load native code, open network connections or hide encoded code |
| **Antivirus** | Microsoft Defender (built into Windows) | ClamAV, if installed (`sudo apt install clamav`) | Known viruses |
| **VirusTotal** (optional, free key) | ✅ | ✅ | Checks the mod against 70+ antivirus engines. Known files are checked instantly by fingerprint; new files up to 200 MB are uploaded for a scan |

**Results:** ✅ safe → added · ⚠️ unusual but not dangerous (shown with the reason; for example a script that can run commands, which some legit mods do) · ⛔ blocked.

To turn on VirusTotal, make a free account at [virustotal.com](https://www.virustotal.com/gui/join-us), click your name → **API key**, and paste it into the installer (Windows: the *VirusTotal key* field; Linux: `sudo beammp virustotal`). The free key allows 4 checks per minute and 500 per day, which is plenty for mods.

> No checker is perfect. These checks stop the common tricks and known malware, but still only use mods from places you trust.

## 🔐 Your keys are encrypted

Your **BeamMP AuthKey**, your **VirusTotal key** and the **mod page password** are never stored in plain text, and never in `ServerConfig.toml`.

- **Windows:** encrypted with Windows' own DPAPI, tied to your Windows account. The file is useless on any other PC or account.
- **Linux:** AES-256 encrypted (`/var/lib/beammp-easyserver/secrets.enc`). The unlock key is a separate root-only file in `/etc/beammp-easyserver`.
- When the server starts, the key is decrypted **in memory only**. On Linux the server gets its config from RAM (`/run`). On Windows it gets a temporary copy in your private AppData folder, and the key is wiped from that copy a few seconds after start-up.
- The server and the mod page run as a separate, unprivileged `beammp` user on Linux, which can't read the keys.

So you can share or back up your server folder and `ServerConfig.toml` without leaking your keys. Change them with `sudo beammp key` / `sudo beammp virustotal` (Linux) or by running the installer again (Windows).

## Adding mods (easy)

Mods are `.zip` files, for example from the BeamNG.drive mod repository. Players who join download them automatically.

### From the dashboard (Linux and Windows)

Open the dashboard's **Mods** page and **drag & drop mod zips onto it**. Each upload is virus-checked first, and a blocked file never reaches the server. From there you can also:
- turn mods on/off without deleting them
- delete mods
- pick a **map mod** as the server map with one click (map mods are detected automatically)

The server **restarts by itself about 15 seconds after any change**, so there's nothing else to do. Note that a restart disconnects anyone who is playing.

Other ways on Linux:
- On the server itself, drop zips into the **`BeamMP-Mods`** folder in your home folder or on your desktop (log out and back in once after installing)
- From the terminal: `beammp addmod ~/Downloads/*.zip`, and change the map with `beammp map italy`

> The mod page is for your home network only. Do **not** port-forward port 30815.

### Windows: drag & drop onto the desktop icon

Drag mod `.zip` files onto **Drop BeamMP Mods Here** on your desktop. It copies them in, offers to switch to the map if the mod contains one, and restarts the server for you. Double-clicking the icon opens the mods folder.

Mods folder locations: `C:\BeamMP-Server\Resources\Client` (Windows) and `/opt/beammp-server/Resources/Client` (Linux).

## Changing the map

Run the installer again, or edit `ServerConfig.toml`:

```toml
Map = "/levels/west_coast_usa/info.json"
```

Built-in maps: `gridmap_v2`, `west_coast_usa`, `east_coast_usa`, `utah`, `italy`, `jungle_rock_island`, `industrial`, `small_island`, `automation_test_track`, `hirochi_raceway`, `johnson_valley`, `derby`, `driver_training`

---

## 🗺️ Roadmap

Ideas for future versions (not built yet):

- **AI troubleshooting assistant**: reads the server log and explains errors in plain English with suggested fixes (today the Logs page has simple built-in hints)
- **Plugin ecosystem**: let developers add their own pages and tools to the dashboard
- More analytics: per-map statistics and mod download stats

Suggestions are welcome; open an issue.

## How it's built (security)

- Linux: the game server runs as `beammp` and the dashboard as `beammp-dash`. Each can only touch its own files. The few admin jobs (start/stop, updates, saving encrypted keys, firewall) go through a tiny root helper that only accepts a fixed list of actions.
- Keys are encrypted at rest (AES-256 on Linux, DPAPI on Windows) and only decrypted in memory.
- The dashboard uses only Python's standard library: no third-party packages to keep updated.

## ❤️ Support the project

BeamMP EasyServer is free. If it saved you some time, you can buy me a coffee using the **Sponsor** button at the top of this page. Thank you!

## License

MIT. See [LICENSE](LICENSE). The BeamMP server itself is licensed separately by the BeamMP team.
