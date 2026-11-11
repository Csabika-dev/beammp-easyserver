# BeamMP EasyServer

**Host your own BeamNG.drive multiplayer (BeamMP) server in one click, on Windows or Linux.**

No config files, no command line knowledge needed. The installer downloads the newest official BeamMP server, asks a few simple questions (name, map, player count), sets everything up and starts it.

> Not affiliated with or endorsed by the BeamMP team. This only automates the setup of the official [BeamMP server](https://github.com/BeamMP/BeamMP-Server).

---

## Before you start: get your free AuthKey (1 minute)

1. Go to **https://keymaster.beammp.com** and log in with Discord
2. Click **Keys**, then **+**, give it any name
3. Copy the key; the installer will ask for it

---

## Windows

1. Click the green **Code** button → **Download ZIP**, then extract it
2. Open the `windows` folder and double-click **`Install-BeamMP-Server.bat`**
3. Click **Yes** when Windows asks for permission
4. Fill in the window (paste your AuthKey) and press **Install**

That's it. You get a **Start BeamMP Server** shortcut on your desktop.

It also handles:
- A **Drop BeamMP Mods Here** desktop icon: drag mod zips onto it (each one is virus-checked first)
- Your AuthKey and VirusTotal key are stored **encrypted**
- Microsoft Visual C++ Runtime (installed automatically if missing)
- Windows Firewall rules for the server port
- Optional auto-start when you log in

| File | What it does |
|---|---|
| `Install-BeamMP-Server.bat` | Install, or change settings later (run it again) |
| `Add-Mods.bat` | Drag mod .zip files onto it (same as the desktop icon) |
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

### Option B: double-click

1. Download the ZIP and extract it
2. In the `linux` folder, double-click **`install.sh`** and choose **Run in Terminal**
   (or double-click **Install BeamMP Server** and allow launching it)
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
- Installs a simple `beammp` command to manage it

### Managing the server

```
beammp status      is it running?
beammp logs        live server console (Ctrl+C to leave)
beammp restart     restart (also: start / stop)
beammp config      edit name, map, key... then auto-restart
beammp mods        list mods + mod page address and password
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

### Linux server: upload from any PC or phone at home

The installer turns on a small **mod upload page**. On any computer or phone on your home Wi-Fi, open:

```
http://<server-ip>:30815
```

Log in (`admin` plus the password shown at the end of the install; run `beammp mods` to see it again) and **drag & drop mod zips onto the page**. Each upload is virus-checked first, and a blocked file never reaches the server. From there you can also:
- turn mods on/off without deleting them
- delete mods
- pick a **map mod** as the server map with one click (map mods are detected automatically)

The server **restarts by itself about 15 seconds after any change**, so there's nothing else to do. Note that a restart disconnects anyone who is playing.

Other ways on Linux:
- On the server itself, drop zips into the **`BeamMP-Mods`** folder in your home folder or on your desktop (log out and back in once after installing)
- From the terminal: `beammp addmod ~/Downloads/*.zip`, and change the map with `beammp map italy`

> The mod page is for your home network only. Do **not** port-forward port 30815.

### Windows server: drag & drop onto the desktop icon

Drag mod `.zip` files onto **Drop BeamMP Mods Here** on your desktop. It copies them in, offers to switch to the map if the mod contains one, and restarts the server for you. Double-clicking the icon opens the mods folder.

Mods folder locations: `C:\BeamMP-Server\Resources\Client` (Windows) and `/opt/beammp-server/Resources/Client` (Linux).

## Changing the map

Run the installer again, or edit `ServerConfig.toml`:

```toml
Map = "/levels/west_coast_usa/info.json"
```

Built-in maps: `gridmap_v2`, `west_coast_usa`, `east_coast_usa`, `utah`, `italy`, `jungle_rock_island`, `industrial`, `small_island`, `automation_test_track`, `hirochi_raceway`, `johnson_valley`, `derby`, `driver_training`

---

## ❤️ Support the project

BeamMP EasyServer is free. If it saved you some time, you can buy me a coffee using the **Sponsor** button at the top of this page. Thank you!

## License

MIT. See [LICENSE](LICENSE). The BeamMP server itself is licensed separately by the BeamMP team.
