# Changelog

## 1.15.0 - Vehicle rules, server plugins, Mac support (experimental) - Rolling release only, not in Stable yet

<!-- website: the "New in" cards on the website. One per line, "Title: text". Not shown on GitHub.
Vehicle rules: Block props, trailers or any car, and stop spawn spam. Mod cars heavy enough to lag everyone are found automatically.
Server plugins: Install community game modes like CareerMP, freeRoamMP and BeamJoy, straight from each author's page.
Run it as a team: Invite friends with a link that works once and expires after an hour, and choose what each one can do on each server. They can sign in with Discord.
-->

- **Host on a Mac** (macOS 13+, Apple Silicon or Intel): `curl -fsSL https://raw.githubusercontent.com/Csabika-dev/beammp-easyserver/main/mac/install.sh | bash`. BeamMP has no macOS server, so EasyServer runs the official Linux server in a small Lima VM that starts with your Mac and can't see your files. The Mac passes the game ports (TCP + UDP) and the dashboard on to the VM, can keep the game port open on your router with UPnP (checked every 20 minutes), and can keep itself awake while plugged in. The dashboard shows your Mac's address in invites and on the Health page. The BeamMP-only guard isn't available on a Mac. Update by running the command again; `--uninstall` removes it.
- **Vehicle rules** (Config): block props, big physics props (crushers, spinners, containers …), trailers, or any car by name, or allow only certain cars (one-make racing). Set a wait between spawns and a limit on spawns per minute to stop spawn spam. Presets: *Anything goes*, *No chaos*, *Racing*, *Roleplay*. Admins can be exempt. The server refuses a blocked car before anyone sees it and tells the player why - no restart, nothing for players to download.
- **Auto-detection:** EasyServer looks inside your car mods and counts how complex each car is, so heavy cars (the ones that make everyone's game slower) and prop / trailer mods are recognised and can be blocked in one click - new mods are covered as soon as you add them. The Config page also lists which cars and props players really spawn on your server (last 7 days) with a Block button, and what was refused lately.
- **Missing-mod warning** (Mods): a mod that only adds parts to a car that isn't in the game or your other mods gets a "needs the mod for …" badge - it does nothing on its own.
- **Server plugins** (Mods → Server plugins): install community plugins - CareerMP, freeRoamMP, BeamJoy Sandbox (Revived), BeamMP Environment Sync, CobaltEssentials - straight from their authors' GitHub pages. You see what goes where (server folders, client mods) before anything is installed; client mods get the virus check; plugins can be updated, turned off and on, or removed, and Lua errors are shown next to each one. Plugins you copied in by hand show up too. Installing from a .zip file is possible after confirming you trust the author. Owner only, because plugins run with the server's rights. Each plugin is credited to its author with a link and its licence; the list lives in `docs/plugins.json`, so anyone can suggest one.
- **Mod pack code** (Mods → Share code): a short text code with your BeamNG repository mods instead of a big file. Another EasyServer pastes it and gets the same mods, downloaded one by one and virus-checked.
- **Run the server as a team** (Settings → Users & roles):
  - **Invite links:** pick a role → send a link → they choose their own name and password. One use, expires after 1 hour, revocable.
  - **Custom roles** with tick-boxes: Players, Start & stop, Maps & events, Mods, Server config, Dashboard settings.
  - **Per-server access:** a different role on each server, or no access at all to some.
  - **From the internet:** chosen accounts can log in from anywhere when they have their own two-step login (set up under **My account**, or while accepting an internet invite). Revoking it logs them out at once.
  - **My account** (click your name): change your own password, set up or turn off your two-step login.
  - **Sign in with Discord** (team members, not the owner): the owner turns it on under Users & roles, each member links their Discord once under **My account**, then signs in with one button. Discord only replaces the password - two-step login and the internet rules stay the same. It goes through a small sign-in service run by the project (`login-service/`), which stores nothing.
  - On a Mac, team members log in from your home network only (there every visitor looks like a home device, so the internet rule couldn't be enforced).
- **Player reports:** players type `/report name what happened` in the game. You get an alert (dashboard, Discord, email, phone - whatever is set up) with the chat just before it, admins in the game see it right away, and reports wait on the Players page until someone marks them handled. On by default; one report a minute per player.
- **The dashboard in 5 languages:** English, Deutsch, Español, Magyar and Polski. Pick one on the login screen or at the bottom of the sidebar (it starts in your browser's language when there is a translation). Each language is a plain file in `dashboard/lang/` - fix a word on GitHub, or add a language by adding a file (see `dashboard/lang/README.md`; `python3 tools/i18n.py` shows what's still missing). Messages that come from the server itself (errors, health checks, log explanations) are still English for now.
- **Kick words** (Config → Moderation): a list of words that get a player removed the moment they write one - kicked, or banned for 1 hour, 1 day, 7 days or forever, your choice. Works even with the chat filter off, matches whole words only ("ass" doesn't catch "class"), never removes admins, and the ban shows up in the dashboard like any other.
- **Vote kick** (off by default, Config → Moderation): when no admin is online, `/votekick name reason` and `/yes` from more than half of the other players kicks someone for 10 minutes. Needs at least 4 players online (adjustable), admins can't be voted out, new arrivals can't vote, one vote per player every 5 minutes.
- **Chat history** (Players page): search the game chat by word or player and see what was said around any message, including messages players didn't see because of a mute or the chat filter. Kept on the server computer only (up to 10 MB), can be turned off or deleted. Moderators and up can read it.
- **Mod sets** (Mods): save the mods that are on now under a name, like "Drift night" or "Canyons cruise", and switch between sets in one click. Mods outside the set are turned off, not deleted, and light mode keeps working with every set.
- **Disk space on the Mods page:** how much room the mods take, how much is free on that drive (with a warning when it's almost full), and a **Biggest first** sort to find what to clear out. An upload that won't fit is refused with a clear message instead of filling the disk.
- **New website:** a short tour of the dashboard at the top, setup as four steps you click through, the main features side by side with their screenshots, copy buttons on every install command, and questions that open in place. The Help page groups its answers by topic and opens the matches as you search. The site is in English, German, Spanish, Hungarian and Polish: it opens in your browser's language and a picker in the top bar switches it. Sections slide in as you scroll, and headlines, feature rows and buttons animate when you point at them. It's built with React from `site/`, still works without JavaScript and respects "reduce motion".
- **"New in" on the Overview:** after an update the dashboard shows what's new in that version, in your language, until you press **Got it**. The website's "New in" section and this panel both come from a short hidden block in this changelog, so a release updates both by itself.
- **The dashboard runs on React now**, like the website: every page (Overview, Servers, Config, Mods, Players, Health, Updates, Logs, Notifications and Settings), logging in, the menu, server picker and security alerts. It looks and works the same, in the same languages. Pages now open straight away: the dashboard fetches them quietly in the background after you log in and remembers what each page showed, and while something is still loading you see the page's shape shimmering instead of "Loading…". The German, Spanish, Hungarian and Polish dashboard is now 99% translated. Its source is in `dashboard/ui`; the page is built from it automatically.
- **Glass look for the dashboard** (and the phone app, which shows the dashboard): frosted, see-through panels over a soft blue and orange glow, rounder buttons, and a floating menu bar on phones. It's the new default, in light and dark. The palette button at the bottom of the sidebar (or "Classic look" in the phone menu) switches back to the old look. If your system asks for less transparency, the panels turn solid.
- **Calmer pages:** a page slides in once when you open it. Parts that finish loading or refresh later appear in place instead of sliding in again, and saving something keeps your place on the page instead of jumping back to the top.
- **Games page** (new in the menu): everything players start themselves in the chat, with the results and leaderboards in one place. Lap times moved here from the Players page.
  - **Races:** `/race Canyon run 3` starts a 3-lap race on a track; everyone types `/race join` within 30 seconds, then a 5-second countdown. Checkpoints count in order, positions come from each car's own clock, results are announced with the gaps. Anyone or only admins can start one.
  - **Cops and robbers:** `/cnr start` (or `/cnr start 15` for 15 minutes), then `/cnr join` - add `cop` or `robber` to ask for a side. About one in three are cops; robbers get a 30-second head start. A cop busts a robber by staying within 10 m while the robber is stopped for 3 seconds. Cops get a hint where the nearest robber is every 30 seconds, robbers a warning when a cop gets close. No teleporting during a game. Distance, time and what happens to a busted robber can be changed.
  - **Speed traps:** an admin parks on a straight and types `/trap new Main straight`. Everyone driving through sees their speed; a new record is announced. `/trap` shows the fastest.
  - **Badges:** 13 to earn - first lap, track record, race wins, busts, getaways, 200 km/h, 100 and 1000 km, night owl and more. Announced in the chat, shown in player profiles, `/badges` in the game.
  - **Monthly seasons** (off by default): on the 1st, each leaderboard's winner is kept and gets a badge, and lap times, speed traps and win counts start again from zero. `/season` shows what's left and the last winners.
  - **On screen in the game:** the next checkpoint is drawn on the road as a tall coloured beam (yellow for a checkpoint, green for the lap or finish line, blue for the start), with a faint one for the checkpoint after it. A small panel at the top shows your race time, lap, position and how far the next checkpoint is, a big countdown before the start, and your result at the end. Timed laps outside races get the same timer with your best lap. In cops and robbers, COP (blue) and ROBBER (red) float above the players' cars, and your panel shows your side, the time left, how many robbers are free and a bar while a cop is stopping a robber. This comes with the small helper mod players already download for `/tp` and the chat suggestions, which is now also handed out whenever races, cops and robbers or lap times are on.
  - **Game chat in your language** (Config → Welcome message & announcements): pick German, Spanish, Hungarian or Polish, and everything the server says in the game - races, cops and robbers, votes, warnings, `/help`, the command hints while typing, badges - and the text on players' screens switches to it within 30 seconds. Your own welcome message and announcements are sent exactly as you write them.
  - **Championships:** start one on the Games page with a name ("Winter Cup") and every race with 2 or more drivers gives points by finishing place - 25-18-15-12-10-8-6-4-2-1, or 10-8-6-5-4-3-2-1. The points are announced after each race, players see the standings with `/champ`, and the page shows the table with wins and podiums. Starting a new one or ending it keeps the leader as the winner under Past championships.
  - **Raspberry Pi:** the Linux installer now notices the 32-bit Raspberry Pi OS (which on a Pi 4/5 looks 64-bit from the outside) and says to use the 64-bit one, instead of downloading a server that can't start. A Pi with less than 2 GB of memory gets a warning to keep it small.
  - **Set up other computers at home from the dashboard** (Servers → Other computers at home, owner only): the dashboard finds them on your network by itself and installs EasyServer on them over SSH, with the progress shown live and the new dashboard password at the end. **Update** later is one click: the password you type isn't saved; the dashboard leaves its own SSH key there instead. Works with:
    - **Raspberry Pi 4/5** (64-bit Raspberry Pi OS).
    - **Mini PCs and NAS boxes** with Ubuntu, Debian or OpenMediaVault (64-bit). TrueNAS, Unraid and Synology don't allow installing programs and are told so.
    - **Windows PCs** with Windows' own OpenSSH Server turned on (the page shows how). The install runs `install.ps1 -Unattended`, which has no setup window, keeps an earlier install's settings and makes a dashboard password. Log in with an administrator account.
  - **Ready-to-go Raspberry Pi SD card** (dashboard on Windows): put a microSD card in the PC, type your Wi-Fi and a user + password for the Pi, press **Make the card**. The dashboard downloads Raspberry Pi OS Lite (64-bit) from Raspberry Pi, checks it against their checksum before anything is erased, and writes it to the card after Windows asks you for permission. It also adds the settings for the Pi's first start: Wi-Fi, user, SSH on, and the dashboard's key. Start the Pi with the card and it shows up in the dashboard by itself and gets EasyServer installed. Only removable cards are offered. The Wi-Fi password goes on the card only as the WPA key made from it, and the Pi password only as a one-way hash; neither is stored in the dashboard. A Wi-Fi set to WPA3 only isn't supported (WPA2 and WPA2/WPA3 are).
  - **All your computers** (Servers, owner only): this computer and every computer set up from here, in one list. It shows whether each server runs, its players and map, and has **Start / Stop / Restart** for each. The dashboard reaches them with its own SSH key and leaves the command in that computer's dashboard folder; that dashboard carries it out within 10 seconds. Computers with an older EasyServer say to press Update first.
  - **Move this server to another computer** in one go (All your computers → **Move this server here**). The settings, mods, bans, allow-list, moderation, stats, championships, lap times, drift and race results go over. The other computer saves a backup of its own server first, checks every mod for viruses, puts everything in place and starts it. Then the server on this computer stops, and it stays off there, even after that computer restarts, until you press Start there and confirm (the Discord bot won't start it either). The AuthKey stays on the computer it was typed on; you're told when the new one still needs it.
  - **Backup copies** (Settings → Automatic backups → **Keep a copy somewhere else**): after every backup a copy goes to a USB drive or folder, or to another computer set up from here, and the last 7 are kept there. If this computer's disk dies, the backups survive. A failed copy (for example a USB drive that isn't plugged in) sends a notification.
  - **How long joining takes** (Mods): under the download size players see how long a new player waits for the mods, from your upload speed (or the mod download limit if it's lower), and which few mods are most of it.
  - **Health report:** new checks for backups that are only on this computer (or a failed copy), how long joining takes with your upload speed, and a server that was moved away. Problems have a **Fix it** button that opens the right page.
  - **Settings in three sizes:** **Normal** (notifications, phone app, password, backups), **Advanced** (adds security alerts, the team, two-step login, internet access, Discord bot, integrations, sleep and moving the server) and **Everything**. Your choice is remembered in that browser. The quick search (Ctrl+K) always finds every setting and shows them all.
  - The **Other computers at home** card stays small when there's nothing on your network; **Show** opens it.
  - **Google Drive backups** (Settings → Automatic backups → Google Drive): press **Connect Google Drive**, type the short code it shows at google.com/device and press Allow - like signing in on a TV, no password goes through the dashboard. Every nightly backup is then copied to a "BeamMP EasyServer backups" folder in your Drive and the last 7 of each server are kept. Before you connect it says how much space that takes; after, how much the copies use and how much of your Drive is free, with a warning when it's nearly full. EasyServer can only see the files it made itself (Google's `drive.file` access), nothing else in your Drive. **Rescue:** on a new computer, connect the same Google account and press **Restore** next to any backup in the Drive, even one from the old computer. The Health report counts the Drive as a copy somewhere else. Needs a Google app ID: the project's own, or your own (the steps are on the page).
  - **Events, bigger:** besides weekly, an event can be on **one date**. It can switch on a **game** while it runs (races, drift points or cops and robbers) and switch it off again after, and post the **results to Discord** when it ends: who came, the fastest laps and best drifts set during the event. A one-off event turns itself off when it's done. The Events card shows the last event's results.
  - **Public server page, bigger** (Settings → Public status page): an **About** text and a **Join our Discord** button, how long the first join takes, the next 5 events with their game, and the championship standings and best drifts on the current map (when lap times are public). Shared links show a preview with the title, players and map in Discord, WhatsApp and the like.
  - **Discord:** `/player name` shows a player's time played, last seen, best laps, best drift, championship place, top speed and badges, across all your servers. `/leaderboard` shows lap records, best drifts, the championship or the most played.
  - **Player profiles across servers:** a player's profile also lists their time, last visit, best lap and best drift on your other servers.
  - **Server templates, bigger:** two new ones (**Cops and robbers**, **Off-road**), and every template also switches on the games and lap times that fit and offers to open the mod browser with a matching search. The template in use is marked.
  - **Mods players don't use** (Mods): vehicle mods nobody spawned in the last 30 days, map mods for maps that aren't played (not the current map, rotation or an event) and mods that hold the same car twice, with how much download and joining time turning them off saves, and a **Turn off** button for each.
  - **Mod updates** (Mods): **Update all** downloads and virus-checks every repository mod that has a newer version in one go, and **Install updates by themselves** does it for you while nobody is playing - a running server restarts for them, and you get a notification with what changed.
  - **Drift scoring** (Games → Game rules, off until you turn it on): players get points for every second they slide sideways - more for a bigger angle and more speed - shown big on their screen. Straighten up and the drift is banked, hit something and it's lost. Each map has its own leaderboard on the Games page and with `/drift`, and a new record is announced to everyone. Scores no real drift could give are refused, and nothing counts during a race or cops and robbers.
  - **Live map:** every car on the map with a short trail, your tracks and speed traps, cops and robbers marked - updated every second while you look at it.
  - **Weekly recap** (off by default): once a week a short post to your Discord (or Telegram / webhook) about the week - who played most, new records, races, chases and badges. You see the post before it goes out and can send it by hand.
- **Lap times** (Games → Lap times): admins make a track in the game - `/track new <name>` at the start line, `/track cp` at each checkpoint, then `/track done` for a loop or `/track finish` for a sprint. Every lap on it is timed with the car's own game clock (lag doesn't change the time), skipping a checkpoint doesn't count, new records are announced in the chat and players see the top 3 with `/laps`. The dashboard shows the top 10 of each track, and can rename or delete tracks and clear or remove times. The best times can also go on the public status page.
- **Player profiles:** click any player's name on the Players page to see their play time, when they were first and last seen, their kicks, bans, mutes and reports, their best laps, and private notes your team writes about them ("warned twice about ramming").
- **Performance graphs** (Health page): processor, memory, upload, players and the players' average ping over the last 24 hours or 7 days, kept when the dashboard restarts. You get a notification when the players' ping stays above 250 ms for 5 minutes.
- **Quick search:** press Ctrl+K (⌘K on a Mac), or the search button, and type what you're looking for - "port", "ban", "backup", "laps" - to jump straight to that page and setting.
- **"Get your server ready" checklist** on the Overview: name the server, add an AuthKey, add mods, check friends can reach it, invite friends, get alerts on your phone. Each step ticks itself off when it's done, and you can skip steps or hide the list.
- **How to join, on the status page:** BeamMP has no links that open the game, so the public status page now says how to join - the name to search in the server list, and (if you turn it on) the address for Direct Connect, which is the relay's address when "Hide my IP" is on.
- **Undo instead of "Are you sure?"** when you delete a mod, a mod set or a plugin, clear the notifications or delete the chat history. It disappears at once and the message at the bottom offers **Undo** for a few seconds. Empty pages say what goes there and offer the button to add the first one, and a page or card that can't load says why and has a **Try again** button.
- **The dashboard moves more:** pages slide in when you open them, and buttons, cards and the menu react when you point at them, like on the website. Turned off when your computer asks for less motion.
- **Restore a nightly backup in one click** (Settings → Automatic backups, owner only): no more downloading it and importing it again. How things are right now is saved as a backup first, so a restore can be undone. If the backup has mods in it, you choose whether to put those back too.
- **Sleep PC** button on the Overview page (and so on the first screen of the phone app): puts the server computer to sleep in one tap, after asking. Wake it with the app's **Wake up** button or its power button. Shown to the owner and admins.
- Fixed: **Put the computer to sleep** did nothing on Windows (it failed before asking Windows, and still said it worked). It now sleeps, or says why Windows refused.
- **Check new mods**: the mod check button on the Mods page now only checks mods that are new or changed since their last check (mods were already only checked once when added). **Check all again** still checks every mod, e.g. after your antivirus got new virus definitions.
- **"Hosted with BeamMP EasyServer"**: a small link at the bottom of the public status page and one line at the end of the **Copy invite** message, so players who want their own server can find it. One tick-box turns it off (in the invite window, or on the status page settings).
- **Credits** section in the README for everything EasyServer builds on.
- Linux: `Resources/Server` is now writable for the dashboard (needed for plugins) - run the installer once more to update an existing install.
- **Security (found in a review of every feature):**
  - Mac: the dashboard no longer gives "you're sitting at the server" trust to local connections on a Mac (there, every device arrives through the Mac's port forwarder as a local address), and "Internet access" to the dashboard can't be switched on. Don't forward the dashboard port on a Mac.
  - Wake helper (Windows): the downloaded Python must carry the Python Software Foundation's signature before it's used, like in the main installer.
  - Website: the visit counter script is pinned to a fixed version with an integrity check, so a changed script can't run on the download page.

## 1.14.0 - One-click port forwarding, invites, mod browser

- **Only open the port when it's needed** (the new default): the router port opens when you copy an invite, press Open, or a friend types `/join` in your Discord, stays open while anyone plays and closes 30 minutes after the last player leaves. "Always open" is one click away on the Health page.
- **Discord `/join`**: anyone in your Discord server can open the server for 2 hours. You get a notification saying who did.
- **Two versions from now on: Stable and Rolling, both free for everyone.** Stable is the tested one (the release marked *Latest*, the `stable` branch). The Rolling release is the newest code as soon as it's made - pick it on the Updates page → **Version** and the dashboard tells you when a newer one is out (it may have bugs; installing Stable over it keeps your settings and mods). EasyServer is fully free for now: the supporter licence box is hidden.
- **BeamMP-only guard** (Settings → Security, off by default): port scanners and bots knock on any open port and hang up within a second, real players stay connected. An address that keeps knocking without ever staying to play is blocked by the firewall - 1 hour, then 6 hours, then a day if it comes back. Your home network and anyone who has played on the server are never blocked, and you can unblock an address (or mark a friend's IP as "never block") in one click. On Linux the root helper adds the nftables rules; on Windows a small firewall task (set up by the installer, runs as SYSTEM from a folder only administrators can change) does it.
- **Automatic port forwarding** (Health page): "Open port 30814 automatically" asks your router to forward the game port (TCP + UDP) to this computer with UPnP - no router settings page. Every server's port is opened, the forward is checked every 20 minutes and put back after a router restart, and turning it off closes it again. If the router has UPnP switched off, or another device already uses the port, it says so and what to do instead. Off while "Hide my IP" is on (not needed there).
- **Copy invite** (Overview): a ready-to-paste message for Discord or WhatsApp with the server name, the address and port for Direct Connect, the map, players online and the mod download size. Switch to "Same Wi-Fi" for friends at home, and add your own line (rules, a Discord link). With "Hide my IP" on it uses the relay address.
- **Mod browser** (Mods → Browse mods): look through the official BeamNG mod repository by category (vehicles, maps, skins, props ...) sorted by downloads, rating or date, search it, or paste a link to any mod page - then **Install**. The mod is downloaded, virus-checked like an upload and ready for players; mods you already have are marked.
- **New logo** in the dashboard, the phone app icon and the website.
- **The installer asks how friends outside your home should get in**, in plain words: *Do it for me* (the dashboard opens the game port on your router only when needed - the new default), *I'll do it myself* (the install window shows your router's address, the port and what to type in, and the help page opens), or *Not now*. Changeable later on the Health page.
- Fixed: the Windows installer said "The dashboard did not start" when the dashboard was running with HTTPS on.


## 1.13.0 - Command suggestions in the chat

- **Command suggestions**: when players type `/` in the game chat, a list of this server's commands appears above the chat box with what each one does. It narrows down as you type and also finds typos (`/rpeair` shows `/repair`). **Tab** completes, **↑ ↓** choose, **Esc** closes. Admins also see the admin commands. On by default (Config → In-game tools); players get it through the same tiny helper mod as /tp and /repair (about 4.5 KB).
- **"Did you mean ...?"**: a mistyped command (`/tpacept`, `/hlep`, `/kik`) gets a private hint with the right command instead of being posted in the chat for everyone. Commands that aren't close to any EasyServer command are left alone, so other plugins' commands keep working.
- **/help** now lists every command that's switched on, one per line with what it does.

## 1.12.1 - Stay logged in

- **Stay logged in on this device** (login page): your own phone or computer logs in by itself for 30 days after the last visit - also after the dashboard or the computer restarts. On by default in the Android app, off in browsers. Only a fingerprint of each device is stored, never the login itself.
- **Remembered devices** (Settings): see every phone and browser that stays logged in, with when and from where it was last used; forget one you lost, or all of them. Logging out, changing the password, or deleting an account forgets its devices. Extra accounts' devices only work on your home network, like their passwords.
- **Password managers**: the browser now offers to save the dashboard password (Chrome, Edge, Firefox, Safari, and Google / Samsung autofill on Android).
- **Android app**: keeps you logged in when the app is closed.
- **HTTPS fix**: with HTTPS on, opening `http://` (for example the desktop shortcut or an old bookmark) showed "connection reset". It now goes to the `https://` address instead.

## 1.12.0 - Teleport, repair, light mode

- **In-game tools** (Config, off by default): `/tp name` with `/tpaccept` / `/tpdeny` and a wait between teleports; repairing set to Normal, Realism (reset keys off, `/repair` every few minutes) or Hardcore (no resets, no repairs). Uses a 2 KB helper mod that EasyServer adds and removes by itself and players download automatically.
- **Light mode for map mods** (Mods page): players only download the map mod of the map being played; the others come back by themselves when their map is picked (Config, vote, rotation, events). Shows how much download it saves.
- **Map statistics** (Players page): hours played, players, average stay, peak and time on for every map, for 7 / 30 / 90 days.
- **Log explainer** (Logs page): "Explain the whole log" groups every error and warning with what it means and what to do; click a red or yellow line to explain it. The automatic hints use the same, much bigger list.
- **Status page**: now also lists the mods and the download size (can be turned off).

**Security fixes** (found by attacking a test install):
- Log explainer: a player could slow the dashboard down for many seconds by writing specially crafted chat (chat ends up in the server log). Lines are now cut to 400 characters, the patterns are bounded and reading stops after 4 seconds.
- An AuthKey written with single quotes, triple quotes or a lower-case `authkey` was not hidden in diagnostic reports and the config history (which viewers can read). Every TOML form is hidden now.
- A modified game client could fire the plugin's internal timer events (fake player counts in the statistics, a lot of disk writes, skipping countdowns). The plugin now ignores timer events sent by players.
- The custom alert webhook can only reach internet addresses - not this computer, the home network or cloud-internal addresses - and doesn't follow redirects.
- `/tp` requests have a 15-second cooldown and one open request per player, so nobody can flood someone's chat with them.
- Guests never get admin rights or the maintenance bypass, even with an admin's name.
- Chat bridge: players can't post disguised links (`[free mods](https://...)`) into your Discord any more.
- Wake helper: refuses `/start` when it was paired before a Discord server was picked, instead of answering in any Discord server.
- Windows installer: the downloaded Python and Visual C++ files must carry a valid signature from the Python Software Foundation / Microsoft before they run, and get random temp names.
- Mods named after reserved Windows devices (`CON.zip`, `NUL.zip` ...) are refused.

## 1.11.0 - Admin tools

- **Server health report** (the Network page is now **Health**): internet connectivity, the BeamMP backend, the server process, the game port, config, AuthKey, stats plugin, mods, outside reachability, disk and memory - each Passed / Warning / Failed with the fix. Checked every 30 minutes; when something starts failing you get a notification and a **diagnostic report** is saved (the last 10 are kept, downloadable, with keys, passwords and addresses removed).
- **Connection doctor**: "Someone can't join?" - type a name and it explains why their last join failed and what to do.
- **Users & roles** (Settings, owner only): extra logins for moderators (kick, mute, ban, who can join, restart, maintenance), viewers (read-only) and admins. Extra accounts only work from your home network; the user list is signed against tampering. Every request is checked against the role.
- **Activity log** (Logs page): who did what and when, from the dashboard, Discord and the game, including logins.
- **Maintenance mode** (Players page): only admins and listed players can join, everyone else gets your message; online players get a 10-second warning. Shown in the Discord status message and on the status page.
- **Security presets** (Config): Most secure, Public but safe, Friends only, Open to everyone, Weak computer.
- **What changed?** (Config): the last 40 versions of the config with who changed it, a setting-by-setting comparison (also between two servers) and one-click restore.
- **Copy a server**: create a new server as a copy of an existing one (config, who can join, moderation, bans, messages, events, restarts).
- **Announcements at set times** (Config) - in the game chat and optionally Discord.
- **Advertise events automatically** (Settings): posted to Discord / Telegram / webhook when planned and the day before, plus in-game reminders in the last 3 hours.
- **Telegram and webhook alerts** (Settings): Telegram through your own bot (finds the chat by itself) and any incoming webhook - Slack, Mattermost, Rocket.Chat, Google Chat, Teams, Home Assistant, n8n, Zapier ...
- **Public status page** (Settings, off by default): `/status` and `/status.json` with state, players, map, next event and 30-day uptime. No login, no addresses.
- **Modpack** (Mods page): download all enabled mods as one .zip with checksums, and import a modpack into another server (virus-checked).

## 1.10.0 - Sleep & wake-up

- **Auto-sleep** (Settings -> Sleep & wake-up, off by default): the server computer goes to sleep when nobody has played for 5 minutes to 24 hours, optionally only between certain hours. It never sleeps while someone is online, an event runs or starts within 30 minutes, the dashboard is being used or a server is being started from Discord. **Sleep now** button and `/sleep` in Discord (Manage Server only).
- **Wakes up by itself** 10 minutes before every scheduled event and optionally every day at a set time (Linux: the computer's alarm clock; Windows: a wake timer).
- **Wake-on-LAN**: the dashboard finds the network cable adapter, shows its MAC address and turns Wake-on-LAN on (Linux: ethtool, kept on after reboots and by NetworkManager; Windows: adapter power settings, asks for permission). Warns on Wi-Fi, with BIOS tips.
- **Wake-on-LAN compatibility score** (0-100): checks the network cable, the network chip, whether Wake-on-LAN is on and stays on after a restart, the sleep mode (classic S3 / deep or modern S0 / s2idle), whether a laptop is plugged in, a way to wake it from outside, and whether it has ever woken up. Every problem says exactly what has to be changed.
- **Router guide** with the steps for FRITZ!Box, ASUS, TP-Link, Ubiquiti, MikroTik, OpenWrt, Netgear and others.
- **Wake helper** (new, optional): a small program for a Raspberry Pi or any always-on PC at home. While the server computer sleeps it answers `/start` and `/status` in Discord and the **Wake up** button in the phone app, from anywhere and without port forwarding. Paired with a code from the dashboard; "Test the helper" checks it. `BeamMP-EasyServer-WakeHelper.zip` is attached to every release.
- **Android app**: when the server doesn't answer it shows a **Wake up** button (Wake-on-LAN on the home Wi-Fi, the wake helper from anywhere). Scan the QR code again to get it.
- The installed web app (iPhone home screen) shows a "server is asleep" page with a Wake up button instead of a broken dashboard.
- After waking up the dashboard reconnects the Discord bot, updates DuckDNS and the live status message (which says "asleep" while the computer sleeps). New notification type "Sleep and wake-up" (off by default).
- Linux: the installer now installs `ethtool`. A laptop set to "never sleep" still never sleeps by itself - only auto-sleep and Sleep now can put it to sleep.

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
