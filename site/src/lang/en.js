// All text on the website, in English. Other languages copy this file and translate the text.
// Markup: **bold**  *italic*  `code`  [link text](address). {GH} is the GitHub project,
// {LATEST} the latest release, {ASK} the "ask a question" page. Keep the structure the same.
export default {
  meta: {
    home: {
      title: "BeamMP EasyServer - host a BeamNG.drive multiplayer server in one click",
      description: "Free one-click installer and web dashboard for BeamMP (BeamNG.drive multiplayer) servers on Windows and Linux. Mods with virus check, player stats, moderation, Discord, phone app.",
      ogTitle: "BeamMP EasyServer",
      ogDescription: "Host your own BeamNG.drive multiplayer server in one click - and run it from your phone.",
    },
    features: {
      title: "Features - BeamMP EasyServer",
      description: "What BeamMP EasyServer does: guided setup, a dashboard you can use from your phone, virus-checked mods, vehicle rules, server plugins and team accounts. Free for Windows and Linux.",
      ogTitle: "BeamMP EasyServer - features",
      ogDescription: "Host a BeamMP server for your friends without editing config files.",
    },
    help: {
      title: "Help & community - BeamMP EasyServer",
      description: "Answers to the most common BeamMP EasyServer questions: friends can't join, port forwarding, mods, slow joining, forgotten password, Discord bot, crashes. Ask the community if yours isn't here.",
      ogTitle: "BeamMP EasyServer - Help & community",
      ogDescription: "Common questions with ready answers, and a community forum for everything else.",
    },
    privacy: {
      title: "Privacy policy - BeamMP EasyServer",
      description: "What BeamMP EasyServer, its website and the Discord sign-in helper do with personal data. No telemetry: your server's data stays on your own computer.",
      ogTitle: "BeamMP EasyServer - Privacy policy",
      ogDescription: "No telemetry. Your server's data stays on your own computer.",
    },
  },

  nav: {
    start: "Get started", what: "What it does", downloads: "Downloads", faq: "FAQ",
    features: "Features", help: "Help", language: "Language", privacy: "Privacy",
  },

  common: {
    // "What's new": {v} is the version from CHANGELOG.md.
    newTitle: "New in {v}", newRolling: "In Rolling now. They come to Stable once they've been tested.", newStable: "Out now in the Stable version.",
    download: "Download",
    copy: "Copy", copied: "Copied", pressCtrlC: "Press Ctrl+C",
    license: "MIT license. Not made by or affiliated with the BeamMP team or BeamNG GmbH. EasyServer builds on their work and on many mod and plugin authors: [see the credits]({GH}#-credits).",
    tryTitle: "Try it on your PC",
    viewOnGithub: "View on GitHub",
    downloadFor: "Download for {os}",
    downloadVFor: "Download {v} for {os}",
    setupFor: "Set up on {os}",
    macRolling: "Mac: Rolling version (experimental)",
    onPhone: "Download for your PC",
    otherSystems: "Other systems and versions",
    themeDark: "Switch to dark mode",
    themeLight: "Switch to light mode",
  },

  tour: {
    label: "Dashboard pages",
    tabs: ["Overview", "Mods", "Players", "Status page"],
    alts: [
      "The EasyServer dashboard: server running, 7 of 16 players online, map, uptime and who's online",
      "Mods page with virus check results and light mode saving 380 MB",
      "Player statistics: players per day, busiest hours and week overview",
      "Public status page with 30-day uptime",
    ],
  },

  home: {
    h1: "Your own BeamNG.drive multiplayer server, set up in one click",
    lead: "EasyServer installs the official BeamMP server and gives you a dashboard for it on your PC or phone. Add mods, see who's playing and keep trolls out, without config files or a command line. It's free and open source, for Windows and Linux.",
    how: "How it works",

    startTitle: "Get started",
    startSub: "About ten minutes, most of it waiting for downloads.",
    stepsLabel: "Setup steps",
    back: "Back",
    next: "Next:",
    steps: [
      { short: "AuthKey", title: "Get a free AuthKey",
        text: ["Log in at [keymaster.beammp.com](https://keymaster.beammp.com) with Discord, click **Keys**, then **+**, and copy the key. It puts your server in the public BeamMP list."] },
      { short: "Install", title: "Install",
        text: ["This installs the tested **Stable** version. For the newest features, see [Rolling](#versions)."] },
      { short: "Dashboard", title: "Open the dashboard",
        text: ["On the server computer, go to **http://localhost:30815** and choose a password. From your phone or another PC at home, use **http://<server-ip>:30815**."] },
      { short: "Friends", title: "Let friends in",
        text: ["On the Health page, click **Open port automatically**. Most routers accept it. If yours doesn't, forward port 30814 (TCP and UDP) yourself, and the Health page tells you when it works.",
          "Then click **Copy invite** and paste it in Discord. [Step-by-step guides]({GH}#-guides)"] },
    ],
    osLabel: "Your system",
    windows: "Windows", linux: "Linux",
    winInstall: "Download **BeamMP-EasyServer-Windows.zip** from the [latest release]({LATEST}), extract it and double-click **Install-BeamMP-Server.bat**.",
    linuxInstall: "Paste this into a terminal:",
    videoTitle: "How to make a BeamMP server in 5 minutes - setup video",
    videoNote: "Rather watch? The whole setup takes about 2 minutes. [Open on YouTube](https://youtu.be/DWD9HcW1OIc)",

    whatTitle: "What it does",
    whatSub: "Made for people who want to play with friends, not learn server admin. [All features](features.html)",
    featuresLabel: "Features",
    features: [
      { title: "Mods without the worry",
        alt: "Mods page with virus check results and light mode saving 380 MB",
        text: "Drag mod zips onto the page. Each one is checked for hidden programs, disguised files and zip bombs with Microsoft Defender or ClamAV, and VirusTotal if you like, before players can download it.",
        list: ["**Mod browser:** install from the BeamNG repository in one click, and update the same way",
          "**Light mode:** players only download the map being played, so joining is faster",
          "**Modpacks:** move or share all your mods as one file"] },
      { title: "See who plays, and when",
        alt: "Player statistics: players per day, busiest hours and week overview",
        text: "Players per day, the busiest hours, a week heatmap, top players, server records and the maps people actually stay on.",
        list: ["**Kick, mute and ban** from the dashboard, Discord or game chat",
          "**Maintenance mode** closes the server while you work on it",
          "**Team accounts** for friends who help, with only the permissions you give them"] },
      { title: "Choose how open it is",
        alt: "Security presets: Most secure, Public but safe, Friends only, Open to everyone, Weak computer",
        text: "One click sets your server anywhere from **Most secure** (invite-only, anti-bot, flood protection) to **Open to everyone**. Every config change is saved, so you can see what changed and undo it.",
        list: ["**Invite list,** because BeamMP has no join password",
          "**Anti-bot:** join codes, guest blocking and connection limits"] },
      { title: "Run it from your phone",
        alt: "The dashboard on a phone",
        text: "The dashboard works in any phone browser. There's an Android app, and on iPhone you can add it to the home screen.",
        list: ["**Alerts** for crashes, joins and updates on your phone, Discord, Telegram, Slack or email",
          "**Discord bot** with /status, /start, /restart, /whitelist and a chat bridge",
          "**Sleep and Wake-on-LAN,** so the PC doesn't have to run all day"] },
      { title: "A status page for players",
        alt: "Public status page with 30-day uptime",
        text: "One link shows whether the server is up, who's online, which mods to download and the next event. No login, and no addresses or settings on show." },
    ],

    alsoTitle: "Also included",
    alsoSub: "All optional. Turn on what you need.",
    also: [
      ["Copy invite", "A ready-to-paste Discord message with the address and port."],
      ["Map vote and rotation", "Players type /vote, or the map changes on a schedule."],
      ["Weekly events", "\"Friday drift night\" switches map and mods and is announced in Discord."],
      ["/tp and /repair", "Teleport to friends once they accept, with realism or hardcore repair rules."],
      ["Car cleanup", "Abandoned cars are removed, with a countdown before the nightly cleanup."],
      ["Chat tools", "Welcome message, timed announcements, a chat filter, anti-spam and /countdown."],
      ["Several servers", "Run more than one server on one PC, each with its own CPU, RAM and download limits."],
      ["Nightly backups", "Restore, or move to a new computer, with one file."],
      ["Hide your IP", "An optional relay and flood protection against DDoS."],
      ["Log explainer", "Server errors in plain English, with what to do about them."],
    ],

    secTitle: "Security",
    secSub: "Your server is a computer on your home network, so this matters.",
    security: [
      ["Keys are encrypted", "Your AuthKey, tokens and passwords are never stored in plain text."],
      ["Separate users on Linux", "The game server and the dashboard each run as their own limited user."],
      ["Two-step login", "Required before the dashboard can be reached from the internet."],
      ["Tested on every change", "Automated tests try to break into every dashboard page and the game plugin on each update."],
    ],

    dlTitle: "Downloads",
    dlSub: "Both are free. Not sure? Take Stable.",
    stable: "Stable",
    stableWhat: "Tested. It's the release marked \"Latest\" on GitHub.",
    stableWin: "**Windows:** download **BeamMP-EasyServer-Windows.zip**, extract it and double-click **Install-BeamMP-Server.bat**",
    linuxLabel: "**Linux:**",
    stableButton: "Download Stable",
    rolling: "Rolling",
    rollingWhat: "New features as soon as they're made. May have bugs.",
    rollingWin: "**Windows:** download the ZIP, extract it, open the **windows** folder and double-click **Install-BeamMP-Server.bat**",
    mac: "**Mac (experimental, Rolling only):** paste this into Terminal. It runs the server in a small Linux VM that starts with your Mac ([how it works]({GH}#mac-experimental)).",
    broken: "Something broken? Install Stable over it. Your settings and mods stay.",
    rollingButton: "Download Rolling (ZIP)",
    changes: "What changed in each version: [changelog]({GH}/blob/main/CHANGELOG.md), [all releases]({GH}/releases)",

    faqTitle: "Questions",
    faqSub: "[More answers and the community](help.html)",
    faq: [
      ["Is it free?", "Yes. It's free and open source (MIT license), with every feature and no ads. BeamMP and its server are free too. You need your own copy of BeamNG.drive to play."],
      ["Is this the official BeamMP server?", "EasyServer installs the **official** BeamMP server and keeps it updated. EasyServer itself is a community project, not made or endorsed by the BeamMP team."],
      ["What computer do I need?", "Any 64-bit Windows 10 or 11 PC, or Linux (Ubuntu, Linux Mint, Debian and others, including a Raspberry Pi 4 or 5 with a 64-bit OS). An old laptop is enough for a group of friends. Upload speed matters more than the processor."],
      ["Does it change my router?", "Only if you click **Open port automatically**, which asks your router to open the game port. Otherwise it just opens the port in the computer's own firewall, and asks first."],
      ["Can I use it from my phone?", "Yes. The dashboard works in any phone browser, there's an Android app, and you can add it to the iPhone home screen. Managing it from outside your home works once HTTPS and two-step login are on."],
      ["I found a bug or have an idea", "[Open an issue on GitHub]({GH}/issues/new/choose). For security problems, please use private reporting instead."],
    ],

    closing: "Download it, run it and follow the steps. If you get stuck, the Help page and the community can help.",
    footnote: "Screenshots show a demo server with invented players.",
  },

  features: {
    h1: "Host BeamMP for your friends without touching a config file",
    lead: "EasyServer installs the official BeamMP server, then gives you one page to run it from. It's free, open source and works on Windows and Linux.",
    howInstall: "How to install",
    onPage: "On this page",
    online: "Getting it online", onlineSub: "The part most people get stuck on.",
    onlineRows: [
      ["Guided setup", ["Paste your AuthKey and the installer checks it's valid. It sets the server to start with your PC and restarts it if it crashes."]],
      ["Opening the port", ["One click asks your router to open port 30814. If your router doesn't allow that, the Help page explains how to do it by hand."]],
      ["“Why can't my friend join?”", ["The Health page checks your AuthKey, the port, the firewall and whether your server shows up in the BeamMP list, and tells you which one is wrong."]],
      ["Old laptops welcome", ["The Weak computer preset allows fewer players and cars and clears abandoned cars quickly, so a spare laptop can run a small server."]],
    ],
    running: "Running it", runningSub: "From your desk or from the sofa.",
    playersAlt: "Players page with a list of online players and kick, mute and ban buttons",
    playersCap: "The Players page",
    phoneAlt: "The dashboard on a phone",
    phoneCap: "Same thing on a phone",
    runningRows: [
      ["Start, stop, change map", ["Change the map from a list instead of editing ServerConfig.toml. Works in any browser, including on your phone."]],
      ["Players and bans", ["Kick, mute and ban from the dashboard, from Discord or with a chat command. There's also an invite-only list and maintenance mode."]],
      ["Mods", ["Drag a zip onto the page or pick one from the BeamNG repository. Each one is virus-scanned before players download it.", "Share your whole mod list with a short code, and a friend's server can install the same set."]],
      ["Backups and alerts", ["Back up and restore your config. Get a message on Discord, email, Telegram or your phone when the server crashes."]],
    ],
    closing: "Download it, run it and follow the steps. Most people are online in about five minutes. If you get stuck, the Help page and the community can help.",
    footnote: "The Mac version is experimental and only in Rolling.",
  },

  help: {
    h1: "Help & community",
    lead: "The questions server owners ask most, with answers. Not here? Ask in the community forum.",
    search: "Search, e.g. “friends can't join” or “mods”",
    searchLabel: "Search questions",
    topicsLabel: "Topics",
    all: "All",
    question: "question", questions: "questions", match: "match",
    results: "Results", marked: "Matching words are marked.",
    mostAsked: "Most asked",
    copyLink: "Copy link to this answer", linkCopied: "Link copied",
    empty: "No answer matches that yet. [Ask it in the forum]({ASK}) and it may end up here.",
    askTitle: "Didn't find your answer?",
    askText: "Ask the community. Search old threads, share ideas, or show off your server. You only need a free GitHub account.",
    askButton: "Ask a question",
    forumButton: "Open the forum",
    cats: {
      start: "Getting started", join: "Joining & network", mods: "Mods & maps",
      dash: "Dashboard & login", discord: "Discord & alerts", trouble: "Problems",
    },
    // id, topic, question, answer blocks (a string is a paragraph; {ul: []} and {ol: []} are lists), most asked
    qa: [
      ["what-do-i-need", "start", "What do I need to host a server?", [
        { ul: ["A computer that stays on while you play: any 64-bit Windows 10/11 PC, or Linux (Ubuntu, Linux Mint, Debian, also a Raspberry Pi 4/5 with a 64-bit system). An old laptop is fine for a group of friends.",
          "A free BeamMP **AuthKey** (see the next question).",
          "Your own copy of BeamNG.drive to play. The server itself is free."] },
        "Upload speed matters more than the processor: every player downloads your mods from you."]],
      ["authkey", "start", "Where do I get the AuthKey?", [
        { ol: ["Go to [keymaster.beammp.com](https://keymaster.beammp.com) and log in with Discord.",
          "Click **Keys**, then **+**, and give it any name.",
          "Copy the key and paste it into the installer, or later under **Config → AuthKey**."] },
        "Without a key the server still works on your home network, it just isn't in the public server list. One key per public server."]],
      ["windows-or-linux", "start", "Should I use Windows or Linux?", [
        "**Playing on the same PC you host on?** Windows is the easiest: download the zip, double-click **Install-BeamMP-Server.bat**.",
        "**A spare computer just for the server?** Linux is better. The server runs in the background, starts by itself when the computer boots, restarts after a crash, and with **laptop mode** keeps running with the lid closed. One command installs everything."]],
      ["update", "start", "How do I update EasyServer and the BeamMP server?", [
        { ul: ["**EasyServer itself:** the dashboard's **Updates** page. On Windows you can also run the newest installer over the old one; your settings are kept.",
          "**The BeamMP server:** **Config → Restarts & updates → install BeamMP updates** updates it automatically at the scheduled restart. By hand: `beammp update` on Linux, **Update-BeamMP-Server.bat** on Windows."] }]],

      ["not-in-server-list", "join", "My server doesn't show up in the BeamMP server list", [
        { ol: ["**Config → AuthKey** must be filled in.",
          "**Config → Private** must be off. The \"Most secure\" and \"Friends only\" presets hide the server on purpose.",
          "The port must be reachable from the internet (see the next question).",
          "Give it a minute or two after starting."] },
        "**Health → Check again** checks all of this and says which one is wrong."]],
      ["friends-cant-join", "join", "Friends on my Wi-Fi can join, but friends outside my home can't", [
        "Your router has to let them in. This is a one-time setting:",
        { ol: ["In your router, give the server computer a fixed address (often called *DHCP reservation* or *static lease*).",
          "**Forward port 30814, TCP and UDP**, to that computer. Search for \"*your router model* port forwarding\" for the exact menu.",
          "In the dashboard: **Health → Full check**. \"Reachable from the internet\" should be green."] },
        "Still red? Some internet providers share one address between many homes (CGNAT), so port forwarding can't work. The Health page tells you when that's the case: ask your provider for a public IPv4 address, or use a relay (**Settings → Hide your IP**)."], true],
      ["one-player-cant-join", "join", "One specific player can't join", [
        "**Health → Someone can't join?** → type their BeamMP name → **Check**. It reads their last attempt and says why it failed: banned, not on the invite list, maintenance, guests blocked, anti-bot code, too many players from one connection, server full, and so on, with the fix.",
        "Refused players also show up under **Config → Who can join → Recently refused** with a **+ allow** button."]],
      ["password", "join", "How do I put a password on my server / make it friends-only?", [
        "BeamMP has no join password, so EasyServer uses an **invite list** instead:",
        { ol: ["**Config → Who can join**: turn on the list and type your friends' BeamMP usernames, one per line.",
          "**Save list**. It works right away, no restart."] },
        "Everyone else gets an \"invite-only\" message. The quickest way is the **Most secure** or **Friends only** preset under **Config → Security presets**. With the Discord bot: `/whitelist add name`."]],
      ["ip-changes", "join", "My home IP address keeps changing", [
        "Set up a free fixed name: **Settings → Fixed address (DuckDNS)**. Friends then connect to `yourname.duckdns.org`, and it keeps working when the address changes. Public servers don't need this: the server list always has the current address."]],
      ["hide-ip", "join", "Can players see my home IP? What about DDoS?", [
        "Players connect to your server, so yes, they can find the address, like with any self-hosted game server. If that worries you, **Settings → Hide your IP** sends players through a relay, and flood protection is part of the **Most secure** and **Public but safe** presets. See [Protect your IP]({GH}/blob/main/PROTECT-YOUR-IP.md)."]],

      ["add-mods", "mods", "How do I add mods?", [
        { ol: ["Open **Mods** in the dashboard and drag the mod **.zip** files onto the page.",
          "Each one is virus-checked first. The server restarts about 15 seconds later (on Windows, press Restart). That disconnects players, so add mods when it's quiet.",
          "Map mods get a **map:** badge. Click **Use map** to play it."] },
        "Players don't install anything: BeamMP downloads the mods for them when they join. Also possible: the **Drop BeamMP Mods Here** desktop icon (Windows), the `BeamMP-Mods` folder or `beammp addmod file.zip` (Linux)."]],
      ["slow-joining", "mods", "Joining takes forever because of the mod download", [
        { ul: ["Turn on **Light mode** on the Mods page: players only download the map that's being played. Other map mods come back by themselves when you switch to their map.",
          "Remove mods nobody uses. The card at the top of the Mods page shows the total download.",
          "Friends on slow internet can get a **modpack** (Mods → Modpack) and copy the files into `Documents\\BeamNG.drive\\mods\\multiplayer` before joining."] },
        "Your upload speed is the limit here, so a big modpack is slow on any home connection."]],
      ["mod-blocked", "mods", "A mod was blocked by the virus check. Is it really dangerous?", [
        "EasyServer blocks mods that contain programs, disguised files or zip bombs, or that Microsoft Defender, ClamAV or VirusTotal flag. A normal BeamNG mod is only car, map and script files, so a blocked mod contains something a mod shouldn't. The reason is shown next to it.",
        "Blocked files never reach the server or your players. Download the mod again from the official BeamNG repository instead of a reupload site."]],
      ["change-map", "mods", "How do I change the map, or let players vote?", [
        { ul: ["**Now:** **Overview → Map**, pick one, confirm. The server restarts on the new map.",
          "**Vote:** **Config → Map vote**, tick the allowed maps. Players type `/vote` in the game chat.",
          "**Automatically:** **Config → Map rotation** (every 1-24 hours) or **Config → Events** (\"Friday drift night\")."] }]],

      ["forgot-password", "dash", "I forgot the dashboard password / lost my phone for two-step login", [
        { ul: ["**Windows:** double-click **Reset-Dashboard-Login.bat** in the EasyServer folder.",
          "**Linux:** `sudo beammp reset-login`"] },
        "Then open the dashboard **on the server computer** and choose a new password. Two-step login is turned off, so set it up again with your new phone."]],
      ["connection-reset", "dash", "The browser says “connection reset” or “not secure”", [
        "**\"Connection reset\":** HTTPS is on, but you opened an `http://` address. Use `https://`, or update to 1.12.1 or newer, which sends you there automatically.",
        "**\"Not secure\" / certificate warning:** normal the first time. Your dashboard makes its own certificate, so the browser doesn't know it yet. Compare the fingerprint shown in **Settings** with the one in the browser warning, then continue. The Android app remembers it for you."]],
      ["phone", "dash", "Can I manage the server from my phone, or from outside my home?", [
        "**At home:** open `http://<server-ip>:30815` on your phone, or install the Android app (**BeamMP-EasyServer.apk** from the [latest release]({LATEST})) and scan the QR code under **Settings → Phone app**. iPhone: Safari → Share → Add to Home Screen.",
        "**From anywhere:** turn on HTTPS and two-step login, use a password of 12+ characters, then **Settings → Access from the internet** and forward port **30815 (TCP)**."]],
      ["stay-logged-in", "dash", "Can it remember my password so I don't log in every time?", [
        "Yes (version 1.12.1 and newer). Turn on **Stay logged in on this device** on the login page. That device then logs in by itself for 30 days after the last visit, also after restarts. Your browser's password manager also offers to save the password.",
        "Lost a phone? **Settings → Remembered devices → Forget**."]],
      ["team", "dash", "How do I give friends access to help moderate?", [
        "**Settings → Users & roles**: name, role, password → **Add**.",
        { ul: ["**Viewer**: look, change nothing", "**Moderator**: kick, mute, ban, invite list, restart, maintenance", "**Admin**: everything except users, passwords and internet access"] },
        "For in-game moderation only, add their BeamMP names under **Config → Moderation & anti-bot → Admins**. They can then use `/kick`, `/ban` and `/mute` in the game chat."]],

      ["discord-bot", "discord", "How do I set up the Discord bot?", [
        { ol: ["[discord.com/developers/applications](https://discord.com/developers/applications) → **New Application**.",
          "**Installation** → Install Link: **None** → save.",
          "**Bot** → turn **Public Bot** off and **Message Content Intent** on (for the chat bridge) → **Reset Token** → copy.",
          "Dashboard: **Settings → Discord bot** → paste the token, turn it on, **Save**. When it says **Online**, click **Add the bot to your Discord**.",
          "Type `/status` in Discord."] },
        "Never share the bot token with anyone. If it leaks, press Reset Token again."]],
      ["slash-commands", "discord", "The bot is online but the slash commands don't show up", [
        { ul: ["New commands can take a minute. Restart Discord (Ctrl+R on PC).",
          "Check **Settings → Discord bot → Discord server the bot answers in** is set to your server.",
          "`/start`, `/stop`, `/restart` and `/whitelist` only appear for people with **Manage Server**, or the Discord users you allowed."] }]],
      ["alerts", "discord", "Can I get a notification when the server crashes or someone joins?", [
        "Yes, on your phone (free **ntfy** app, **Settings → Phone app**), in Discord, Telegram, Slack and other apps, or by email. Choose what you hear about under **Notify me about**. **Config → Join alerts** posts when chosen players join."]],

      ["crash-lag", "trouble", "The server keeps crashing or lagging", [
        { ol: ["**Logs → Explain the whole log** lists every error in plain English, including broken mods and running out of memory.",
          "**Health** shows memory and disk, and **Settings → Computer load** has 24-hour graphs.",
          "On an older computer, use the **Weak computer** preset, lower Max cars and turn on light mode."] },
        "A crashed server restarts by itself, and you're told if crash notifications are on."]],
      ["undo", "trouble", "I changed a setting and now something is broken", [
        "**Config → What changed?** keeps the last 40 versions of your config, with who changed what. **Compare with now** shows the difference, and **Restore** goes back. Your AuthKey is kept, and you can undo the undo."]],
      ["sleep", "trouble", "Do I have to keep the computer on 24/7?", [
        "No. **Settings → Sleep & wake-up** puts it to sleep when nobody has played for a while and wakes it before events. With **Wake-on-LAN** (network cable needed) friends can wake it with `/start` in Discord or the **Wake up** button in the app. The compatibility score lists what still has to be set."]],
      ["new-computer", "trouble", "How do I move my server to a new computer?", [
        { ol: ["Old computer: **Settings → Backup / move to another computer → Export settings + mods**.",
          "Install EasyServer on the new one, then **Import…** that file.",
          "Paste your AuthKey again: keys and passwords are never put in exports."] },
        "Nightly backups are on by default, and the last 7 can be downloaded any time."]],
      ["get-help", "trouble", "My problem isn't here. How do I get help?", [
        { ol: ["**Health → Download diagnostic report**. Keys, passwords and addresses are removed from it.",
          "[Ask in the community forum]({ASK}) and attach the report. Bugs go to [issues]({GH}/issues/new/choose)."] },
        "Found a security problem? Please use [private reporting]({GH}/security/advisories/new) instead of posting it publicly."]],
    ],
  },
  privacy: {
    h1: "Privacy policy",
    lead: "What BeamMP EasyServer, this website and the Discord sign-in helper do with personal data, in plain words. The short version: EasyServer runs on your own computer and sends nothing about you or your players to us.",
    updated: "Last updated: 26 November 2026. Earlier versions are in the project's history on GitHub.",
    contents: "On this page",
    sections: [
      ["short", "The short version", [
        { ul: [
          "**No telemetry.** The EasyServer software, the phone app and the wake helper have no analytics, no crash reporting and no tracking. We never receive your players' names, chat, IP addresses or stats.",
          "**Your server's data stays on your computer**: player names, chat, stats, bans and logs are files on the PC or Raspberry Pi that runs the server. Only features you turn on yourself (Discord, Google Drive, notifications and the others listed below) send anything elsewhere, and only to the service you set up.",
          "**This website** counts visits with GoatCounter, which uses no cookies and stores no IP addresses. It sets no cookies of its own and shows no ads.",
          "**Discord sign-in** for team accounts goes through a small helper we run. It passes your Discord ID and name back to your dashboard and stores nothing.",
        ] },
      ]],
      ["who", "Who is responsible for what", [
        "**The EasyServer project** (the people who maintain [EasyServer on GitHub]({GH})) is responsible for this website and for the Discord sign-in helper described below.",
        "**The owner of each server** is responsible for the data their own server keeps about its players. EasyServer is software you install and run yourself, like any other program. We don't host your server, can't see it, and have no copy of anything it stores. If you play on someone's server and have a question about your data there, ask that server's owner.",
        "EasyServer is a community project. It isn't made by or affiliated with the BeamMP team or BeamNG GmbH; BeamMP and BeamNG.drive have their own privacy policies.",
      ]],
      ["website", "This website", [
        "The website is hosted on **GitHub Pages**. Like every web host, GitHub receives your IP address and browser details when you open a page and may keep them in its server logs for security; see GitHub's privacy statement.",
        "**Visit counter.** We count visits with [GoatCounter](https://www.goatcounter.com), a privacy-friendly, open-source counter. It records which page was opened, the site you came from, your browser and system type, screen size and an approximate country worked out from your IP address. It sets no cookies and doesn't store your IP address or follow you across sites. We use these totals only to see which pages people find useful (our legitimate interest in improving the site). It also counts clicks on the download and GitHub buttons.",
        "**Latest version.** To show the newest version number, your browser asks the GitHub API for it directly, so GitHub sees your IP address. The answer is kept in your browser's session storage for an hour.",
        "**Video.** The home page has a YouTube video using YouTube's privacy-enhanced mode (youtube-nocookie.com). It loads as you scroll to it, so Google receives your IP address and browser details then, and may store data in your browser once you press play; see Google's privacy policy.",
        "**Saved in your browser.** Your chosen light or dark mode, your language, and your best score in the mini game on the error page are saved in your browser's local storage. They never leave your device; clearing your browser data removes them.",
        "No ads, no advertising or social-media trackers, no selling of data.",
      ]],
      ["software", "The EasyServer software on your computer", [
        "EasyServer keeps its data in its own folder on the computer that runs it (for example `C:\\BeamMP-Server\\EasyServer\\data` on Windows or `/opt/beammp-server/.easyserver` on Linux). This includes:",
        { ul: [
          "**Player activity**: names of players who joined or left, kicks, bans, mutes and why, races, lap times, drift scores, badges, map votes and reports. The event log is trimmed when it reaches 20 MB; records and leaderboards are kept until you reset them.",
          "**Chat history**: on by default, so you can moderate. It's trimmed at 5 MB and can be cleared in the dashboard or turned off in the config.",
          "**IP addresses**: players' addresses are kept only in memory while they're online, for the join limit. The BeamMP-only protection keeps addresses it blocked for up to a day, addresses of known players for 30 days, and a list of blocked addresses. The dashboard's own logs record which address logged in or used it (activity log trimmed at 2 MB).",
          "**Dashboard accounts**: names, password hashes (never the passwords), two-factor keys, linked Discord IDs and remembered devices (forgotten after 30 days unused, 90 days at most).",
          "**Backups**: the last 7 nightly backups per server, with settings, bans, allow-list and optionally stats and mods. Keys and passwords are never put in a backup.",
          "**Notes, notifications and reports** you or your players create, kept up to a fixed number of entries.",
        ] },
        "**Connections it makes by itself.** To keep things up to date, EasyServer contacts GitHub and GitHub Pages (update checks, the plugin list and BeamMP server downloads), beamng.com (mod update checks, can be turned off), BeamMP's server list (to check that your server is listed) and an address lookup service (api.ipify.org, or ifconfig.me if that fails) to find your public address. These services see your computer's IP address and that the request comes from EasyServer. Nothing about your players is sent.",
      ]],
      ["optin", "Features that send data elsewhere (only if you turn them on)", [
        "All of these are off until the server owner sets them up. Each sends data straight from your computer to that service, under that service's own terms:",
        { ul: [
          "**Discord** (webhooks, bot, chat bridge, join alerts, event ads, weekly recaps): sends the messages you choose to your Discord server. They can include player names, chat, stats, ban reasons and, if you enable it, the server address.",
          "**Notifications** by email (your own mail server), Telegram, ntfy or a custom webhook: the notification text, which can include player names.",
          "**Google Drive copies**: nightly backups go to a folder in your own Google Drive. EasyServer asks only for access to the files it creates itself (the `drive.file` permission), reads your Google account email to show which account is connected, and uses this access only to save, list and restore its backups. It doesn't read your other files, share Google data with anyone, or use it for ads. EasyServer's use of information received from Google APIs follows the [Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy), including the Limited Use requirements. Disconnect any time in the dashboard or in your Google account.",
          "**VirusTotal mod check** (your own key): sends a fingerprint of each mod file and uploads files VirusTotal hasn't seen before. VirusTotal shares uploaded files with security researchers.",
          "**DuckDNS**: your chosen domain name and your public IP address, so the name keeps pointing at your server.",
          "**Port forwarding (UPnP)**: talks only to your own router.",
          "**Public status page**: shows the public what you pick: server status, map, mods, events and leaderboards. Online player names and your join address are only shown if you turn them on.",
          "**Raspberry Pi setup**: downloads the system image from raspberrypi.com. The Wi-Fi details you enter are written only to the SD card for the Pi.",
        ] },
      ]],
      ["login", "Sign in with Discord", [
        "Team accounts can sign in to a dashboard with Discord. Because Discord needs a fixed address and a secret that can't be in open-source code, this goes through a small helper the EasyServer project runs on **Cloudflare Workers** (easyserver-login.easyserver-hq.workers.dev).",
        "When you sign in, Discord tells the helper your Discord user ID, username and display name (the `identify` permission only: no email, no servers, no messages). The helper signs this information, sends it straight back to the dashboard you came from, and revokes the Discord token. It has no database and keeps no list of users or sign-ins; it's set up with request logs turned off. Cloudflare handles the connection and sees your IP address; see Cloudflare's privacy policy.",
        "The dashboard then stores your Discord ID and name with your team account, on the owner's computer, until the link is removed.",
      ]],
      ["apps", "Phone app and wake helper", [
        "The **Android app** opens your own dashboard. It needs only internet access, has no analytics or advertising code, and saves on your phone just what it needs to reach and wake your server (the dashboard address and its certificate fingerprint, and the wake-up details).",
        "The **wake helper** runs on a computer you choose. It saves its pairing and your Discord bot token in a file only it can read, and listens for wake-up requests from your ntfy topic and your Discord bot. Its log records who asked to start the server.",
      ]],
      ["owners", "If you run a server: your part", [
        "Your server keeps data about the people who play on it, so privacy laws such as the EU's GDPR may apply to you, especially on a public server. A server just for friends and family is often treated as private use. In practice:",
        { ul: [
          "Tell your players what you keep, for example in the welcome message or on your Discord: names, chat, stats and moderation actions, and whether anything goes to Discord.",
          "Keep only what you need. Turn chat history off if you don't moderate, and keep the public page's player names off unless your players are happy with it.",
          "If a player asks you to delete their data, remove their records, bans, notes and reports, and clear the chat history.",
          "Don't post players' IP addresses publicly. The dashboard hides them until you click.",
        ] },
      ]],
      ["kids", "Children", [
        "EasyServer is a tool for people who host game servers and isn't aimed at children. We don't knowingly collect data from children. BeamNG.drive and Discord have their own minimum ages.",
      ]],
      ["rights", "Your rights and how to reach us", [
        "Under the GDPR and similar laws you can ask what data someone has about you, have it corrected or deleted, and object to its use. For this website and the sign-in helper, we usually hold nothing that identifies you: GoatCounter totals are anonymous and the helper stores nothing. For data on a game server, contact that server's owner.",
        "For privacy questions, [open a discussion on GitHub]({ASK}) without any personal details in it and ask for a private contact, or use [private reporting]({GH}/security/advisories/new) for anything sensitive. You can also complain to the data protection authority in your country.",
      ]],
      ["changes", "Changes", [
        "If EasyServer starts handling data in a new way, this page is updated in the same release and the date at the top changes. Every change can be seen in the project's history on GitHub.",
      ]],
    ],
  },
  notFound: {
    title: "Page not found - BeamMP EasyServer",
    h1: "404: wrong turn",
    joke: "This page crashed harder than a BeamNG car at full speed, and there's no reset button for it.",
    text: "While you're here, see how far you can drive.",
    start: "Press Space or tap the road to start driving",
    again: "Crashed! Press Space or tap to try again",
    best: "Best",
    gameLabel: "Mini game: a car jumping over traffic cones and tyres",
    home: "Back to the home page",
    help: "Help & FAQ",
  },
};
