# Changelog

## 1.4.0 - Cars & chat

New card **Config → Cars & chat**. Everything runs in the server plugin: players don't need to install anything, and changes work without a restart.

- **Scheduled car cleanup - on by default.** Removes all cars every day at 04:00, or every 1, 2, 3, 4, 6, 8 or 12 hours if your server is busy. Players get a countdown in the chat first (30 minutes by default, adjustable), then 15, 10, 5, 2, 1 minute, 30 seconds and 10…1.
- **Remove abandoned cars** (off by default): cars that haven't moved for 5 minutes (adjustable) are removed, with a warning to the owner 1 minute before.
- **Chat commands** (off by default): `/countdown` for races, `/tag` chat tags like `[DRIFT]`, `/top` server records (top speed, distance, longest drive without a reset - also on the Players page) and `/help`.
- **Mods page** shows how much players have to download before joining, and can add it to the server description ("| Mods: 1.2 GB").
- The installer now also updates the plugin on extra servers made in the dashboard (before, only the main server got plugin updates).

## 1.3.0 - Hide your IP (DDoS protection)

New section **Settings → Hide your IP (DDoS protection)**. Everything in it is **off by default**, and the settings page explains the trade-off: much less chance of a DDoS hitting your home, but more lag.

- **Hide my IP:** players join through a relay (playit.gg, a VPN with port forwarding, or your own VPS) instead of your home address. Enter the relay's address and port, and the dashboard, Discord join alerts and the network check give players that address instead of your home IP.
- **Test the relay** checks every server through the relay and shows roughly how long the detour takes.
- The **Network** page checks for leaks while it's on: a router port forward that still exposes your home, or your home IP showing up in the public server list.
- **Flood protection (Linux):** optional per-address limits on the game ports (about 20 new connections a minute, about 1000 packets a second). Floods from single computers are cut off and raise a security alert. Your home network is never limited.
- Flood alerts now suggest restarting your router (most providers then give you a new IP address).
- New guide: [PROTECT-YOUR-IP.md](PROTECT-YOUR-IP.md) - relays, VPNs with port forwarding, WireGuard on a VPS, OpenWrt and what each one really protects against.

## 1.2.3 - QR code for two-step login

- Settings → Two-step login now shows a QR code you can scan with your authenticator app, instead of only a key to type.
- The setup explains that clicking "Set up" again makes a new key (only the key on screen works).

## 1.2.2 - Security fix

- Dashboard: when a request was refused before it was read completely (for example the "create password" form sent twice), the rest of it - which could contain the password - was taken as the start of the next request, shown in an error page and written to the log. Such connections are now closed, error pages no longer repeat what was sent, and the log only records the method and path.
- The "Create password" button can't be clicked twice while it's saving.

**If you set your dashboard password with 1.2.1 or earlier,** update, then change the password under Settings, and on Windows delete `C:\BeamMP-Server\EasyServer\data\dashboard.log`.

## 1.2.1 - Windows fixes

- Windows: the installer now checks that the dashboard really started. If it didn't, it says so and shows the reason.
- Windows: the dashboard writes its messages and errors to `EasyServer\data\dashboard.log` (before, a crash at startup left no trace).
- Windows: the installer finds your public IP address more reliably (it tries three services).

## 1.2.0 - Security release

**Everyone should update.** Run the installer again (Linux: `sudo beammp update` updates only the BeamMP server, so run the install command again; Windows: run `Install-BeamMP-Server.bat` again). Your settings, mods and keys are kept.

### New: security alerts (on by default)
- Alerts for password guessing, websites probing the dashboard ("DNS rebinding"), mods that fail the virus check, tampered game-server files, zip bombs in imported backups and connection floods.
- Sent to every channel you set up: a red banner in the dashboard, Discord, email and (optional) browser pop-ups.
- Repeated every 15 minutes until you click **Got it - stop alerts** (or the link / pop-up). Both switches are under Settings -> Security alerts.

### Security fixes
- **Linux:** a hacked game server or a malicious Lua plugin could use file links to make the system (root) change or take over system files - when the server started, when extra servers were created or deleted, during updates, with the `beammp` command and when re-running the installer. Root now never works on files inside the game server's folders.
- **Windows:** the install folder could be changed by every user of the PC. It is now locked to you, administrators and SYSTEM.
- Dashboard login with two-step codes no longer reveals when the password part was right.
- The dashboard now blocks requests from other websites (DNS rebinding); the first password can only be set on the server computer itself.
- Imported backups can no longer redirect your saved email password to another mail server, and zip bombs are skipped.
- Backups no longer pick up the dashboard's HTTPS key through links planted by the game server.
- Player names are cleaned before they are sent to Discord or email (no fake links or @everyone).
- Lockouts also cover whole networks; connection floods are limited.
- Changing the mail server now asks for the email password again.
