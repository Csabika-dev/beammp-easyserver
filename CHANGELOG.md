# Changelog

## 1.9.0 - Phone app and mod updates

- **Android app**: `BeamMP-EasyServer.apk` is attached to every release (built by GitHub from `android/`). Scan the QR code under Settings -> Phone app with the phone's camera and the app connects to your dashboard. It remembers the dashboard's certificate fingerprint, so it only ever talks to your server - no "unsafe certificate" warnings, and nobody can pretend to be your server.
- **iPhone (and Android without the .apk)**: the dashboard can be added to the home screen and opens full screen with its own icon, like an app.
- **Push notifications on the phone** through the free **ntfy** app (Android and iPhone): every notification you turned on, even when the dashboard isn't open. Scan a QR code to subscribe; the private topic is stored encrypted.
- **Mod update check** (Mods page): mods from the BeamNG repository are checked once a day. When a newer version is out you get a notification and an **Update** button - the new version is downloaded, virus-checked and swapped in. Mods from elsewhere can't be checked.

## 1.8.0 - Discord chat, events and graphs

- **Discord chat bridge** (Settings -> Discord bot): the game chat shows up in your Discord channel, and messages written there appear in the game as `[Discord] name: text`. Commands, muted players and filtered words are never sent, and nobody can be pinged from the game.
- **Live status message**: one message in your Discord channel shows every server, its players, CPU, memory and the next events, and updates itself every minute. Works with just the webhook.
- **New Discord commands**: `/top` (who played the most in the last 30 days), `/events` (what's coming), and `/whitelist add|remove|list|on|off` for people with Manage Server.
- **Scheduled events** (Config -> Events): weekly events like "Friday 20:00 drift night". They're announced in Discord (optionally with @everyone) and the game chat, then the server switches to the event's map and turns on its mods, and switches back when it's over. "End now" stops one early. Map rotation pauses during an event.
- **Graphs** (Settings -> Computer load): processor, free memory, upload and players for the last 24 hours.

## 1.7.0 - Rotation, messages, backups, fixed address

- **Server templates** (Config): one click sets up a Drift, Racing, Roleplay or Chill server - player limit, car cleanup, AFK removal, chat tags, chat rules, welcome message and tips, and optionally the map.
- **Map rotation** (Config, off by default): switch to the next map in your list every 1-24 hours, with a countdown in the chat. Can wait until nobody is online.
- **Welcome message** for new players and **announcements** that go to everyone every 5-120 minutes, in turn. `{name}` and `{players}` are filled in. Work right away, no restart.
- **Nightly backups** (Settings, on by default): every server's settings, allow-list, bans, moderation, messages and rotation are saved at 03:30, optionally with mods. The last 7 are kept; download one or restore it with Import. Export and Import now include these files too.
- **Fixed address with DuckDNS** (Settings): friends join at `yourname.duckdns.org` and it keeps working when your home IP changes. The dashboard updates DuckDNS by itself.
- **Low-resource warnings**: a notification when the computer runs out of memory, the processor is maxed out for 5 minutes, or the server uses almost all of your upload - with a suggested player limit. Enter your upload speed from a speed test for the upload warning.

## 1.6.0 - Discord commands

- **Discord bot** (Settings -> Discord bot, off by default): control your servers from Discord with slash commands.
  - `/status` shows every server with its state, online players, map, CPU, memory and uptime. Anyone in your Discord can use it.
  - `/start`, `/stop` and `/restart` (with a server picker if you run several) only work for people with **Manage Server** in your Discord, or the Discord users you allow in the dashboard. Players in the game get a chat message before a stop or restart.
  - The bot only answers in the one Discord server you pick, so nobody else can use it by adding your bot to their Discord. A server has to be started from the dashboard once (to check its settings) before Discord can start it.
  - It connects out to Discord, so no port forwarding is needed. The bot token is stored encrypted like your other keys.

## 1.5.0 - Moderation, anti-bot, scheduled restarts

- **Moderation (Players page):** see who's online and kick, mute or ban them. Bans for 1 hour to forever, with a reason players see. Ban list with unban. Send a message to the game chat.
- **Admins** (Config -> Moderation) can `/kick`, `/ban`, `/mute`, `/unmute` and `/unban` from the game chat; their bans are saved in the dashboard.
- **Chat filter** and **anti-spam** (off by default).
- **Anti-bot** (off by default): a one-time join check (`/verify 1234` in chat), blocking guests, a limit on players from one internet connection, and a limit on new players per minute (with a security alert). Cloudflare can't protect game servers, so this works inside the game.
- **Scheduled restarts** (off by default): daily or every 1-12 hours, with a countdown in chat or only when nobody is online. Optionally **install BeamMP updates automatically** at that restart.
- **Address change warning:** a notification when this computer's home network address or your public IP changes, with the new address and how to keep it fixed (DHCP reservation).
- New notification switches: moderation, address changes, scheduled restarts.
- **Check the settings before the first start:** the first time you start a server, the dashboard shows its key settings (name, map, public/private, AuthKey, two-step login, internet access, anti-bot, car cleanup...) and you confirm them once.
- **IP addresses are blurred** everywhere in the dashboard (overview, network page, logs, notifications) until you click them - handy when you share your screen or a screenshot.

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
