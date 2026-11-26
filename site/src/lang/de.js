// Website text in German. Same structure as en.js; anything left out shows in English.
export default {
  meta: {
    home: {
      title: "BeamMP EasyServer - dein eigener BeamNG.drive-Multiplayer-Server mit einem Klick",
      description: "Kostenloser Ein-Klick-Installer und Web-Dashboard für BeamMP-Server (BeamNG.drive Multiplayer) unter Windows und Linux. Mods mit Virenprüfung, Spielerstatistiken, Moderation, Discord, Handy-App.",
      ogTitle: "BeamMP EasyServer",
      ogDescription: "Hoste deinen eigenen BeamNG.drive-Multiplayer-Server mit einem Klick - und steuere ihn vom Handy aus.",
    },
    features: {
      title: "Funktionen - BeamMP EasyServer",
      description: "Was BeamMP EasyServer kann: geführte Einrichtung, ein Dashboard fürs Handy, virengeprüfte Mods, Fahrzeugregeln, Server-Plugins und Team-Konten. Kostenlos für Windows und Linux.",
      ogTitle: "BeamMP EasyServer - Funktionen",
      ogDescription: "Hoste einen BeamMP-Server für deine Freunde, ohne Konfigurationsdateien zu bearbeiten.",
    },
    help: {
      title: "Hilfe & Community - BeamMP EasyServer",
      description: "Antworten auf die häufigsten Fragen zu BeamMP EasyServer: Freunde kommen nicht rein, Portweiterleitung, Mods, langsames Beitreten, vergessenes Passwort, Discord-Bot, Abstürze. Frag die Community, wenn deine Frage fehlt.",
      ogTitle: "BeamMP EasyServer - Hilfe & Community",
      ogDescription: "Häufige Fragen mit fertigen Antworten und ein Community-Forum für alles andere.",
    },
  },

  nav: {
    start: "Loslegen", what: "Was es kann", downloads: "Downloads", faq: "FAQ",
    features: "Funktionen", help: "Hilfe", language: "Sprache",
  },

  common: {
    // "What's new": {v} is the version from CHANGELOG.md.
    newTitle: "Neu in {v}", newRolling: "Jetzt in Rolling. Sie kommen nach Stable, sobald sie getestet sind.", newStable: "Jetzt in der Stable-Version.",
    download: "Herunterladen",
    copy: "Kopieren", copied: "Kopiert", pressCtrlC: "Strg+C drücken",
    license: "MIT-Lizenz. Nicht vom BeamMP-Team oder der BeamNG GmbH erstellt oder mit ihnen verbunden. EasyServer baut auf ihrer Arbeit und der vieler Mod- und Plugin-Autoren auf: [zu den Credits]({GH}#-credits).",
    tryTitle: "Probier es auf deinem PC aus",
    viewOnGithub: "Auf GitHub ansehen",
    downloadFor: "Für {os} herunterladen",
    downloadVFor: "{v} für {os} herunterladen",
    setupFor: "Auf {os} einrichten",
    macRolling: "Mac: Rolling-Version (experimentell)",
    onPhone: "Für deinen PC herunterladen",
    otherSystems: "Andere Systeme und Versionen",
    themeDark: "Zum dunklen Design wechseln",
    themeLight: "Zum hellen Design wechseln",
  },

  tour: {
    label: "Dashboard-Seiten",
    tabs: ["Übersicht", "Mods", "Spieler", "Statusseite"],
    alts: [
      "Das EasyServer-Dashboard: Server läuft, 7 von 16 Spielern online, Karte, Laufzeit und wer online ist",
      "Mods-Seite mit Ergebnissen der Virenprüfung und dem Leichtmodus, der 380 MB spart",
      "Spielerstatistik: Spieler pro Tag, die vollsten Stunden und die Wochenübersicht",
      "Öffentliche Statusseite mit der Verfügbarkeit der letzten 30 Tage",
    ],
  },

  home: {
    h1: "Dein eigener BeamNG.drive-Multiplayer-Server, mit einem Klick eingerichtet",
    lead: "EasyServer installiert den offiziellen BeamMP-Server und gibt dir ein Dashboard dafür, am PC oder auf dem Handy. Mods hinzufügen, sehen, wer spielt, und Störenfriede draußen halten - ohne Konfigurationsdateien oder Kommandozeile. Kostenlos und Open Source, für Windows und Linux.",
    how: "So funktioniert's",

    startTitle: "Loslegen",
    startSub: "Etwa zehn Minuten, die meiste Zeit wartest du auf Downloads.",
    stepsLabel: "Einrichtungsschritte",
    back: "Zurück",
    next: "Weiter:",
    steps: [
      { short: "AuthKey", title: "Hol dir einen kostenlosen AuthKey",
        text: ["Melde dich auf [keymaster.beammp.com](https://keymaster.beammp.com) mit Discord an, klicke auf **Keys**, dann auf **+**, und kopiere den Schlüssel. Damit erscheint dein Server in der öffentlichen BeamMP-Liste."] },
      { short: "Installieren", title: "Installieren",
        text: ["Damit installierst du die getestete **Stable**-Version. Die neuesten Funktionen gibt es in [Rolling](#versions)."] },
      { short: "Dashboard", title: "Dashboard öffnen",
        text: ["Öffne auf dem Server-Computer **http://localhost:30815** und wähle ein Passwort. Vom Handy oder einem anderen PC zu Hause nimmst du **http://<Server-IP>:30815**."] },
      { short: "Freunde", title: "Freunde reinlassen",
        text: ["Klicke auf der Seite **Zustand** auf **Port automatisch öffnen**. Die meisten Router machen das mit. Wenn deiner nicht mitmacht, leite Port 30814 (TCP und UDP) selbst weiter - die Zustand-Seite sagt dir, wann es klappt.",
          "Dann auf **Einladung kopieren** klicken und in Discord einfügen. [Schritt-für-Schritt-Anleitungen]({GH}#-guides)"] },
    ],
    osLabel: "Dein System",
    windows: "Windows", linux: "Linux",
    winInstall: "Lade **BeamMP-EasyServer-Windows.zip** aus dem [neuesten Release]({LATEST}) herunter, entpacke es und doppelklicke auf **Install-BeamMP-Server.bat**.",
    linuxInstall: "Füge das in ein Terminal ein:",
    videoTitle: "BeamMP-Server in 5 Minuten erstellen - Einrichtungsvideo (Englisch)",
    videoPlay: "Einrichtungsvideo abspielen (Englisch)",
    videoConsent: "Wird von YouTube geladen, das dann deine IP-Adresse sieht.",
    videoNote: "Lieber zuschauen? Die ganze Einrichtung dauert etwa 2 Minuten. [Auf YouTube öffnen](https://youtu.be/DWD9HcW1OIc)",

    whatTitle: "Was es kann",
    whatSub: "Für Leute, die mit Freunden spielen wollen, nicht Serververwaltung lernen. [Alle Funktionen](features.html)",
    featuresLabel: "Funktionen",
    features: [
      { title: "Mods ohne Sorgen",
        alt: "Mods-Seite mit Ergebnissen der Virenprüfung und dem Leichtmodus, der 380 MB spart",
        text: "Zieh Mod-Zips auf die Seite. Jede wird mit Microsoft Defender oder ClamAV - und auf Wunsch VirusTotal - auf versteckte Programme, getarnte Dateien und Zip-Bomben geprüft, bevor Spieler sie herunterladen können.",
        list: ["**Mod-Browser:** mit einem Klick aus dem BeamNG-Repository installieren und genauso aktualisieren",
          "**Leichtmodus:** Spieler laden nur die gerade gespielte Karte herunter, so geht das Beitreten schneller",
          "**Modpakete:** alle deine Mods als eine Datei umziehen oder teilen"] },
      { title: "Sieh, wer spielt und wann",
        alt: "Spielerstatistik: Spieler pro Tag, die vollsten Stunden und die Wochenübersicht",
        text: "Spieler pro Tag, die vollsten Stunden, eine Wochen-Heatmap, Top-Spieler, Serverrekorde und die Karten, auf denen die Leute wirklich bleiben.",
        list: ["**Kicken, stummschalten und bannen** im Dashboard, in Discord oder im Spielchat",
          "**Wartungsmodus** schließt den Server, während du daran arbeitest",
          "**Team-Konten** für Freunde, die helfen - nur mit den Rechten, die du ihnen gibst"] },
      { title: "Bestimme, wie offen er ist",
        alt: "Sicherheits-Presets: Am sichersten, Öffentlich aber sicher, Nur Freunde, Offen für alle, Schwacher Computer",
        text: "Ein Klick stellt deinen Server irgendwo zwischen **Am sichersten** (nur mit Einladung, Anti-Bot, Flutschutz) und **Offen für alle** ein. Jede Konfigurationsänderung wird gespeichert, so siehst du, was sich geändert hat, und kannst es rückgängig machen.",
        list: ["**Einladungsliste,** weil BeamMP kein Beitrittspasswort hat",
          "**Anti-Bot:** Beitrittscodes, Gäste sperren und Verbindungslimits"] },
      { title: "Steuere ihn vom Handy",
        alt: "Das Dashboard auf einem Handy",
        text: "Das Dashboard funktioniert in jedem Handy-Browser. Es gibt eine Android-App, und auf dem iPhone kannst du es zum Home-Bildschirm hinzufügen.",
        list: ["**Benachrichtigungen** bei Abstürzen, Beitritten und Updates auf dem Handy, in Discord, Telegram, Slack oder per E-Mail",
          "**Discord-Bot** mit /status, /start, /restart, /whitelist und einer Chat-Brücke",
          "**Schlafen und Wake-on-LAN,** damit der PC nicht den ganzen Tag laufen muss"] },
      { title: "Eine Statusseite für Spieler",
        alt: "Öffentliche Statusseite mit der Verfügbarkeit der letzten 30 Tage",
        text: "Ein Link zeigt, ob der Server läuft, wer online ist, welche Mods man braucht und das nächste Event. Ohne Anmeldung, und ohne Adressen oder Einstellungen preiszugeben." },
    ],

    alsoTitle: "Auch dabei",
    alsoSub: "Alles optional. Schalte ein, was du brauchst.",
    also: [
      ["Einladung kopieren", "Eine fertige Discord-Nachricht mit Adresse und Port."],
      ["Kartenabstimmung und -rotation", "Spieler tippen /vote, oder die Karte wechselt nach Zeitplan."],
      ["Wöchentliche Events", "„Freitags-Drift-Abend“ wechselt Karte und Mods und wird in Discord angekündigt."],
      ["/tp und /repair", "Zu Freunden teleportieren, sobald sie zustimmen, mit realistischen oder Hardcore-Reparaturregeln."],
      ["Auto-Aufräumen", "Verlassene Autos werden entfernt, mit Countdown vor dem nächtlichen Aufräumen."],
      ["Chat-Werkzeuge", "Begrüßung, zeitgesteuerte Ansagen, Chatfilter, Anti-Spam und /countdown."],
      ["Mehrere Server", "Mehr als einen Server auf einem PC, jeder mit eigenen Grenzen für CPU, RAM und Downloads."],
      ["Nächtliche Backups", "Wiederherstellen oder auf einen neuen Computer umziehen, mit einer Datei."],
      ["IP verstecken", "Ein optionales Relay und Flutschutz gegen DDoS."],
      ["Log-Erklärer", "Serverfehler in verständlichen Worten, mit dem, was zu tun ist."],
    ],

    secTitle: "Sicherheit",
    secSub: "Dein Server ist ein Computer in deinem Heimnetz, deshalb ist das wichtig.",
    security: [
      ["Schlüssel sind verschlüsselt", "Dein AuthKey, Tokens und Passwörter werden nie im Klartext gespeichert."],
      ["Getrennte Benutzer unter Linux", "Spielserver und Dashboard laufen jeweils als eigener, eingeschränkter Benutzer."],
      ["Zwei-Schritt-Anmeldung", "Pflicht, bevor das Dashboard aus dem Internet erreichbar ist."],
      ["Bei jeder Änderung getestet", "Automatische Tests versuchen bei jedem Update, in jede Dashboard-Seite und das Spiel-Plugin einzubrechen."],
    ],

    dlTitle: "Downloads",
    dlSub: "Beide kostenlos. Unsicher? Nimm Stable.",
    stable: "Stable",
    stableWhat: "Getestet. Das ist das Release, das auf GitHub als „Latest“ markiert ist.",
    stableWin: "**Windows:** **BeamMP-EasyServer-Windows.zip** herunterladen, entpacken und auf **Install-BeamMP-Server.bat** doppelklicken",
    linuxLabel: "**Linux:**",
    stableButton: "Stable herunterladen",
    rolling: "Rolling",
    rollingWhat: "Neue Funktionen, sobald sie fertig sind. Kann Fehler haben.",
    rollingWin: "**Windows:** das ZIP herunterladen, entpacken, den Ordner **windows** öffnen und auf **Install-BeamMP-Server.bat** doppelklicken",
    mac: "**Mac (experimentell, nur Rolling):** füge das ins Terminal ein. Es betreibt den Server in einer kleinen Linux-VM, die mit deinem Mac startet ([so funktioniert's]({GH}#mac-experimental)).",
    broken: "Etwas kaputt? Installiere Stable darüber. Deine Einstellungen und Mods bleiben.",
    rollingButton: "Rolling herunterladen (ZIP)",
    changes: "Was sich in jeder Version geändert hat: [Changelog]({GH}/blob/main/CHANGELOG.md), [alle Releases]({GH}/releases)",

    faqTitle: "Fragen",
    faqSub: "[Mehr Antworten und die Community](help.html)",
    faq: [
      ["Ist es kostenlos?", "Ja. Es ist kostenlos und Open Source (MIT-Lizenz), mit allen Funktionen und ohne Werbung. BeamMP und sein Server sind auch kostenlos. Zum Spielen brauchst du dein eigenes BeamNG.drive."],
      ["Ist das der offizielle BeamMP-Server?", "EasyServer installiert den **offiziellen** BeamMP-Server und hält ihn aktuell. EasyServer selbst ist ein Community-Projekt, nicht vom BeamMP-Team gemacht oder unterstützt."],
      ["Welchen Computer brauche ich?", "Jeden 64-Bit-PC mit Windows 10 oder 11, oder Linux (Ubuntu, Linux Mint, Debian und andere, auch ein Raspberry Pi 4 oder 5 mit 64-Bit-System). Für eine Gruppe Freunde reicht ein alter Laptop. Die Upload-Geschwindigkeit zählt mehr als der Prozessor."],
      ["Ändert es meinen Router?", "Nur wenn du auf **Port automatisch öffnen** klickst - das bittet deinen Router, den Spielport zu öffnen. Sonst öffnet es den Port nur in der Firewall des Computers, und fragt vorher."],
      ["Kann ich es vom Handy aus nutzen?", "Ja. Das Dashboard funktioniert in jedem Handy-Browser, es gibt eine Android-App, und auf dem iPhone kannst du es zum Home-Bildschirm hinzufügen. Von unterwegs geht es, sobald HTTPS und die Zwei-Schritt-Anmeldung an sind."],
      ["Ich habe einen Fehler gefunden oder eine Idee", "[Erstelle ein Issue auf GitHub]({GH}/issues/new/choose). Sicherheitsprobleme bitte stattdessen privat melden."],
    ],

    closing: "Herunterladen, starten und den Schritten folgen. Wenn du hängen bleibst, helfen die Hilfe-Seite und die Community.",
    footnote: "Die Screenshots zeigen einen Demo-Server mit erfundenen Spielern.",
  },

  features: {
    h1: "Hoste BeamMP für deine Freunde, ohne eine Konfigurationsdatei anzufassen",
    lead: "EasyServer installiert den offiziellen BeamMP-Server und gibt dir eine Seite, um ihn zu steuern. Kostenlos, Open Source und für Windows und Linux.",
    howInstall: "Wie man installiert",
    onPage: "Auf dieser Seite",
    online: "Online bringen", onlineSub: "Der Teil, an dem die meisten hängen bleiben.",
    onlineRows: [
      ["Geführte Einrichtung", ["Füge deinen AuthKey ein, und der Installer prüft, ob er gültig ist. Er lässt den Server mit deinem PC starten und startet ihn nach einem Absturz neu."]],
      ["Den Port öffnen", ["Ein Klick bittet deinen Router, Port 30814 zu öffnen. Wenn dein Router das nicht erlaubt, erklärt die Hilfe-Seite, wie es von Hand geht."]],
      ["„Warum kommt mein Freund nicht rein?“", ["Die Zustand-Seite prüft deinen AuthKey, den Port, die Firewall und ob dein Server in der BeamMP-Liste auftaucht, und sagt dir, was davon nicht stimmt."]],
      ["Alte Laptops willkommen", ["Das Preset „Schwacher Computer“ erlaubt weniger Spieler und Autos und räumt verlassene Autos schnell weg, so reicht ein alter Laptop für einen kleinen Server."]],
    ],
    running: "Im Betrieb", runningSub: "Vom Schreibtisch oder vom Sofa aus.",
    playersAlt: "Spieler-Seite mit einer Liste der Spieler online und Knöpfen zum Kicken, Stummschalten und Bannen",
    playersCap: "Die Spieler-Seite",
    phoneAlt: "Das Dashboard auf einem Handy",
    phoneCap: "Dasselbe auf dem Handy",
    runningRows: [
      ["Starten, stoppen, Karte wechseln", ["Wechsle die Karte aus einer Liste, statt ServerConfig.toml zu bearbeiten. Funktioniert in jedem Browser, auch auf dem Handy."]],
      ["Spieler und Banns", ["Kicken, stummschalten und bannen im Dashboard, in Discord oder per Chatbefehl. Dazu gibt es eine Einladungsliste und den Wartungsmodus."]],
      ["Mods", ["Zieh ein Zip auf die Seite oder wähle eins aus dem BeamNG-Repository. Jede Mod wird auf Viren geprüft, bevor Spieler sie herunterladen.", "Teile deine ganze Mod-Liste mit einem kurzen Code, und der Server eines Freundes installiert dieselben Mods."]],
      ["Backups und Benachrichtigungen", ["Sichere deine Konfiguration und stelle sie wieder her. Bekomme eine Nachricht in Discord, per E-Mail, Telegram oder aufs Handy, wenn der Server abstürzt."]],
    ],
    closing: "Herunterladen, starten und den Schritten folgen. Die meisten sind nach etwa fünf Minuten online. Wenn du hängen bleibst, helfen die Hilfe-Seite und die Community.",
    footnote: "Die Mac-Version ist experimentell und nur in Rolling.",
  },

  help: {
    h1: "Hilfe & Community",
    lead: "Die Fragen, die Serverbetreiber am häufigsten stellen, mit Antworten. Nicht dabei? Frag im Community-Forum.",
    search: "Suchen, z. B. „Freunde kommen nicht rein“ oder „Mods“",
    searchLabel: "Fragen durchsuchen",
    topicsLabel: "Themen",
    all: "Alle",
    question: "Frage", questions: "Fragen", match: "Treffer",
    results: "Ergebnisse", marked: "Passende Wörter sind markiert.",
    mostAsked: "Am häufigsten gefragt",
    copyLink: "Link zu dieser Antwort kopieren", linkCopied: "Link kopiert",
    empty: "Dazu gibt es noch keine Antwort. [Frag im Forum]({ASK}), vielleicht landet sie dann hier.",
    askTitle: "Antwort nicht gefunden?",
    askText: "Frag die Community. Durchsuche alte Themen, teile Ideen oder zeig deinen Server. Du brauchst nur ein kostenloses GitHub-Konto.",
    askButton: "Frage stellen",
    forumButton: "Forum öffnen",
    cats: {
      start: "Erste Schritte", join: "Beitreten & Netzwerk", mods: "Mods & Karten",
      dash: "Dashboard & Anmeldung", discord: "Discord & Benachrichtigungen", trouble: "Probleme",
    },
    qa: [
      ["what-do-i-need", "start", "Was brauche ich, um einen Server zu hosten?", [
        { ul: ["Einen Computer, der beim Spielen an bleibt: jeden 64-Bit-PC mit Windows 10/11, oder Linux (Ubuntu, Linux Mint, Debian, auch ein Raspberry Pi 4/5 mit 64-Bit-System). Für eine Gruppe Freunde reicht ein alter Laptop.",
          "Einen kostenlosen BeamMP-**AuthKey** (siehe nächste Frage).",
          "Dein eigenes BeamNG.drive zum Spielen. Der Server selbst ist kostenlos."] },
        "Die Upload-Geschwindigkeit zählt mehr als der Prozessor: Jeder Spieler lädt deine Mods von dir herunter."]],
      ["authkey", "start", "Wo bekomme ich den AuthKey?", [
        { ol: ["Geh auf [keymaster.beammp.com](https://keymaster.beammp.com) und melde dich mit Discord an.",
          "Klicke auf **Keys**, dann auf **+**, und gib ihm einen beliebigen Namen.",
          "Kopiere den Schlüssel und füge ihn in den Installer ein, oder später unter **Konfiguration → AuthKey**."] },
        "Ohne Schlüssel läuft der Server trotzdem in deinem Heimnetz, er steht nur nicht in der öffentlichen Serverliste. Ein Schlüssel pro öffentlichem Server."]],
      ["windows-or-linux", "start", "Soll ich Windows oder Linux nehmen?", [
        "**Du spielst auf demselben PC, auf dem du hostest?** Windows ist am einfachsten: Zip herunterladen, auf **Install-BeamMP-Server.bat** doppelklicken.",
        "**Ein Extra-Computer nur für den Server?** Linux ist besser. Der Server läuft im Hintergrund, startet beim Hochfahren von selbst, startet nach einem Absturz neu und läuft mit dem **Laptop-Modus** auch bei zugeklapptem Deckel. Ein Befehl installiert alles."]],
      ["update", "start", "Wie aktualisiere ich EasyServer und den BeamMP-Server?", [
        { ul: ["**EasyServer selbst:** über die Seite **Updates** im Dashboard. Unter Windows kannst du auch den neuesten Installer über den alten laufen lassen; deine Einstellungen bleiben.",
          "**Der BeamMP-Server:** **Konfiguration → Neustarts & Updates → BeamMP-Updates installieren** aktualisiert ihn automatisch beim geplanten Neustart. Von Hand: `beammp update` unter Linux, **Update-BeamMP-Server.bat** unter Windows."] }]],

      ["not-in-server-list", "join", "Mein Server erscheint nicht in der BeamMP-Serverliste", [
        { ol: ["**Konfiguration → AuthKey** muss ausgefüllt sein.",
          "**Konfiguration → Privat** muss aus sein. Die Presets „Am sichersten“ und „Nur Freunde“ verstecken den Server absichtlich.",
          "Der Port muss aus dem Internet erreichbar sein (siehe nächste Frage).",
          "Gib ihm nach dem Start ein, zwei Minuten."] },
        "**Zustand → Erneut prüfen** prüft das alles und sagt, was davon nicht stimmt."]],
      ["friends-cant-join", "join", "Freunde in meinem WLAN kommen rein, Freunde von außerhalb nicht", [
        "Dein Router muss sie reinlassen. Das ist eine einmalige Einstellung:",
        { ol: ["Gib dem Server-Computer im Router eine feste Adresse (oft *DHCP-Reservierung* oder *statische Zuweisung* genannt).",
          "**Leite Port 30814, TCP und UDP**, an diesen Computer weiter. Such nach „*dein Routermodell* Portweiterleitung“, um das genaue Menü zu finden.",
          "Im Dashboard: **Zustand → Vollständige Prüfung**. „Aus dem Internet erreichbar“ sollte grün sein."] },
        "Immer noch rot? Manche Anbieter teilen sich eine Adresse zwischen vielen Haushalten (CGNAT), dann kann Portweiterleitung nicht funktionieren. Die Zustand-Seite sagt dir, wenn das der Fall ist: Frag deinen Anbieter nach einer öffentlichen IPv4-Adresse oder nutze ein Relay (**Einstellungen → IP verstecken**)."], true],
      ["one-player-cant-join", "join", "Ein bestimmter Spieler kommt nicht rein", [
        "**Zustand → Jemand kann nicht beitreten?** → seinen BeamMP-Namen eingeben → **Prüfen**. Es liest seinen letzten Versuch und sagt, warum er gescheitert ist: gebannt, nicht auf der Einladungsliste, Wartung, Gäste gesperrt, Anti-Bot-Code, zu viele Spieler von einer Verbindung, Server voll und so weiter, samt Lösung.",
        "Abgelehnte Spieler stehen auch unter **Konfiguration → Wer beitreten darf → Kürzlich abgelehnt** mit einem **+ erlauben**-Knopf."]],
      ["password", "join", "Wie setze ich ein Passwort auf meinen Server / mache ihn nur für Freunde?", [
        "BeamMP hat kein Beitrittspasswort, deshalb nutzt EasyServer eine **Einladungsliste**:",
        { ol: ["**Konfiguration → Wer beitreten darf**: Liste einschalten und die BeamMP-Namen deiner Freunde eintragen, einen pro Zeile.",
          "**Liste speichern**. Wirkt sofort, ohne Neustart."] },
        "Alle anderen bekommen eine „Nur mit Einladung“-Meldung. Am schnellsten geht es mit dem Preset **Am sichersten** oder **Nur Freunde** unter **Konfiguration → Sicherheits-Presets**. Mit dem Discord-Bot: `/whitelist add name`."]],
      ["ip-changes", "join", "Meine IP-Adresse zu Hause ändert sich ständig", [
        "Richte einen kostenlosen festen Namen ein: **Einstellungen → Feste Adresse (DuckDNS)**. Freunde verbinden sich dann mit `deinname.duckdns.org`, und das funktioniert weiter, wenn sich die Adresse ändert. Öffentliche Server brauchen das nicht: Die Serverliste hat immer die aktuelle Adresse."]],
      ["hide-ip", "join", "Können Spieler meine IP sehen? Was ist mit DDoS?", [
        "Spieler verbinden sich mit deinem Server, also ja, sie können die Adresse herausfinden - wie bei jedem selbst gehosteten Spielserver. Wenn dich das stört, schickt **Einstellungen → IP verstecken** die Spieler über ein Relay, und der Flutschutz ist Teil der Presets **Am sichersten** und **Öffentlich aber sicher**. Siehe [Schütze deine IP]({GH}/blob/main/PROTECT-YOUR-IP.md) (Englisch)."]],

      ["add-mods", "mods", "Wie füge ich Mods hinzu?", [
        { ol: ["Öffne **Mods** im Dashboard und zieh die Mod-**.zip**-Dateien auf die Seite.",
          "Jede wird zuerst auf Viren geprüft. Etwa 15 Sekunden später startet der Server neu (unter Windows auf Neu starten klicken). Dabei fliegen die Spieler raus, also füge Mods hinzu, wenn wenig los ist.",
          "Karten-Mods bekommen ein **map:**-Abzeichen. Klicke auf **Karte nutzen**, um sie zu spielen."] },
        "Spieler installieren nichts: BeamMP lädt die Mods beim Beitreten für sie herunter. Außerdem möglich: das Desktop-Symbol **Drop BeamMP Mods Here** (Windows), der Ordner `BeamMP-Mods` oder `beammp addmod datei.zip` (Linux)."]],
      ["slow-joining", "mods", "Beitreten dauert ewig wegen des Mod-Downloads", [
        { ul: ["Schalte den **Leichtmodus** auf der Mods-Seite ein: Spieler laden nur die Karte herunter, die gerade gespielt wird. Andere Karten-Mods kommen von selbst zurück, wenn du auf ihre Karte wechselst.",
          "Entferne Mods, die keiner nutzt. Die Karte oben auf der Mods-Seite zeigt den gesamten Download.",
          "Freunde mit langsamem Internet können ein **Modpaket** bekommen (Mods → Modpaket) und die Dateien vor dem Beitreten nach `Documents\\BeamNG.drive\\mods\\multiplayer` kopieren."] },
        "Deine Upload-Geschwindigkeit ist hier die Grenze, ein großes Modpaket ist also über jeden Heimanschluss langsam."]],
      ["mod-blocked", "mods", "Eine Mod wurde von der Virenprüfung blockiert. Ist sie wirklich gefährlich?", [
        "EasyServer blockiert Mods, die Programme, getarnte Dateien oder Zip-Bomben enthalten oder die Microsoft Defender, ClamAV oder VirusTotal melden. Eine normale BeamNG-Mod besteht nur aus Auto-, Karten- und Skriptdateien, eine blockierte Mod enthält also etwas, das nicht in eine Mod gehört. Der Grund steht daneben.",
        "Blockierte Dateien erreichen nie den Server oder deine Spieler. Lade die Mod erneut aus dem offiziellen BeamNG-Repository statt von einer Reupload-Seite."]],
      ["change-map", "mods", "Wie wechsle ich die Karte oder lasse Spieler abstimmen?", [
        { ul: ["**Jetzt:** **Übersicht → Karte**, eine wählen, bestätigen. Der Server startet auf der neuen Karte neu.",
          "**Abstimmung:** **Konfiguration → Kartenabstimmung**, die erlaubten Karten ankreuzen. Spieler tippen `/vote` in den Spielchat.",
          "**Automatisch:** **Konfiguration → Kartenrotation** (alle 1-24 Stunden) oder **Konfiguration → Events** („Freitags-Drift-Abend“)."] }]],

      ["forgot-password", "dash", "Ich habe das Dashboard-Passwort vergessen / mein Handy für die Zwei-Schritt-Anmeldung verloren", [
        { ul: ["**Windows:** Doppelklick auf **Reset-Dashboard-Login.bat** im EasyServer-Ordner.",
          "**Linux:** `sudo beammp reset-login`"] },
        "Öffne dann das Dashboard **auf dem Server-Computer** und wähle ein neues Passwort. Die Zwei-Schritt-Anmeldung ist dann aus, richte sie mit deinem neuen Handy wieder ein."]],
      ["connection-reset", "dash", "Der Browser sagt „Verbindung zurückgesetzt“ oder „nicht sicher“", [
        "**„Verbindung zurückgesetzt“:** HTTPS ist an, aber du hast eine `http://`-Adresse geöffnet. Nimm `https://`, oder aktualisiere auf 1.12.1 oder neuer, das leitet dich automatisch um.",
        "**„Nicht sicher“ / Zertifikatswarnung:** beim ersten Mal normal. Dein Dashboard erstellt sein eigenes Zertifikat, deshalb kennt der Browser es noch nicht. Vergleiche den Fingerabdruck unter **Einstellungen** mit dem in der Browserwarnung und fahre dann fort. Die Android-App merkt ihn sich für dich."]],
      ["phone", "dash", "Kann ich den Server vom Handy oder von unterwegs steuern?", [
        "**Zu Hause:** Öffne `http://<Server-IP>:30815` auf dem Handy, oder installiere die Android-App (**BeamMP-EasyServer.apk** aus dem [neuesten Release]({LATEST})) und scanne den QR-Code unter **Einstellungen → Handy-App**. iPhone: Safari → Teilen → Zum Home-Bildschirm.",
        "**Von überall:** HTTPS und Zwei-Schritt-Anmeldung einschalten, ein Passwort mit 12+ Zeichen nehmen, dann **Einstellungen → Zugriff aus dem Internet** und Port **30815 (TCP)** weiterleiten."]],
      ["stay-logged-in", "dash", "Kann es mein Passwort merken, damit ich mich nicht jedes Mal anmelden muss?", [
        "Ja (ab Version 1.12.1). Schalte auf der Anmeldeseite **Auf diesem Gerät angemeldet bleiben** ein. Das Gerät meldet sich dann bis 30 Tage nach dem letzten Besuch von selbst an, auch nach Neustarts. Auch der Passwortmanager deines Browsers bietet an, das Passwort zu speichern.",
        "Handy verloren? **Einstellungen → Gemerkte Geräte → Vergessen**."]],
      ["team", "dash", "Wie gebe ich Freunden Zugang, damit sie beim Moderieren helfen?", [
        "**Einstellungen → Benutzer & Rollen**: Name, Rolle, Passwort → **Hinzufügen**.",
        { ul: ["**Zuschauer**: ansehen, nichts ändern", "**Moderator**: kicken, stummschalten, bannen, Einladungsliste, Neustart, Wartung", "**Admin**: alles außer Benutzern, Passwörtern und Internetzugang"] },
        "Nur für die Moderation im Spiel trägst du ihre BeamMP-Namen unter **Konfiguration → Moderation & Anti-Bot → Admins** ein. Dann können sie `/kick`, `/ban` und `/mute` im Spielchat nutzen."]],

      ["discord-bot", "discord", "Wie richte ich den Discord-Bot ein?", [
        { ol: ["[discord.com/developers/applications](https://discord.com/developers/applications) → **New Application**.",
          "**Installation** → Install Link: **None** → speichern.",
          "**Bot** → **Public Bot** aus und **Message Content Intent** an (für die Chat-Brücke) → **Reset Token** → kopieren.",
          "Dashboard: **Einstellungen → Discord-Bot** → Token einfügen, einschalten, **Speichern**. Wenn **Online** dasteht, auf **Bot zu deinem Discord hinzufügen** klicken.",
          "Tippe `/status` in Discord."] },
        "Gib den Bot-Token niemals weiter. Falls er doch rauskommt, drück erneut auf Reset Token."]],
      ["slash-commands", "discord", "Der Bot ist online, aber die Slash-Befehle tauchen nicht auf", [
        { ul: ["Neue Befehle können eine Minute brauchen. Starte Discord neu (Strg+R am PC).",
          "Prüfe, ob unter **Einstellungen → Discord-Bot** der Discord-Server, auf dem der Bot antwortet, deiner ist.",
          "`/start`, `/stop`, `/restart` und `/whitelist` erscheinen nur für Leute mit **Server verwalten** oder für die Discord-Nutzer, die du erlaubt hast."] }]],
      ["alerts", "discord", "Kann ich eine Benachrichtigung bekommen, wenn der Server abstürzt oder jemand beitritt?", [
        "Ja, auf dem Handy (kostenlose **ntfy**-App, **Einstellungen → Handy-App**), in Discord, Telegram, Slack und anderen Apps oder per E-Mail. Was du hörst, wählst du unter **Benachrichtige mich über**. **Konfiguration → Beitritts-Benachrichtigungen** meldet, wenn ausgewählte Spieler beitreten."]],

      ["crash-lag", "trouble", "Der Server stürzt ständig ab oder ruckelt", [
        { ol: ["**Protokolle → Das ganze Protokoll erklären** listet jeden Fehler in verständlichen Worten auf, auch kaputte Mods und zu wenig Arbeitsspeicher.",
          "**Zustand** zeigt Arbeitsspeicher und Festplatte, und **Einstellungen → Computerauslastung** hat 24-Stunden-Diagramme.",
          "Auf einem älteren Computer das Preset **Schwacher Computer** nehmen, die maximale Autozahl senken und den Leichtmodus einschalten."] },
        "Ein abgestürzter Server startet von selbst neu, und du bekommst Bescheid, wenn Absturz-Benachrichtigungen an sind."]],
      ["undo", "trouble", "Ich habe eine Einstellung geändert, und jetzt ist etwas kaputt", [
        "**Konfiguration → Was hat sich geändert?** hält die letzten 40 Versionen deiner Konfiguration fest, mit wer was geändert hat. **Mit jetzt vergleichen** zeigt den Unterschied, und **Wiederherstellen** geht zurück. Dein AuthKey bleibt erhalten, und du kannst das Rückgängigmachen rückgängig machen."]],
      ["sleep", "trouble", "Muss der Computer rund um die Uhr laufen?", [
        "Nein. **Einstellungen → Schlafen & Aufwachen** schickt ihn schlafen, wenn eine Weile niemand gespielt hat, und weckt ihn vor Events. Mit **Wake-on-LAN** (Netzwerkkabel nötig) können Freunde ihn mit `/start` in Discord oder dem Knopf **Aufwachen** in der App wecken. Die Kompatibilitätswertung zeigt, was noch eingestellt werden muss."]],
      ["new-computer", "trouble", "Wie ziehe ich meinen Server auf einen neuen Computer um?", [
        { ol: ["Alter Computer: **Einstellungen → Sichern / auf einen anderen Computer umziehen → Einstellungen + Mods exportieren**.",
          "EasyServer auf dem neuen installieren, dann diese Datei mit **Importieren …** laden.",
          "Den AuthKey erneut einfügen: Schlüssel und Passwörter kommen nie in Exporte."] },
        "Nächtliche Backups sind standardmäßig an, und die letzten 7 kannst du jederzeit herunterladen."]],
      ["get-help", "trouble", "Mein Problem ist nicht dabei. Wie bekomme ich Hilfe?", [
        { ol: ["**Zustand → Diagnosebericht herunterladen**. Schlüssel, Passwörter und Adressen werden daraus entfernt.",
          "[Frag im Community-Forum]({ASK}) und hänge den Bericht an. Fehler gehören in die [Issues]({GH}/issues/new/choose)."] },
        "Ein Sicherheitsproblem gefunden? Bitte nutze die [private Meldung]({GH}/security/advisories/new), statt es öffentlich zu posten."]],
    ],
  },
  // Translations of the "What's new" cards, by version. The cards themselves come from the
  // <!-- website --> block in CHANGELOG.md; when a new version has no translation here yet, it shows in English.
  whatsNew: {
    "1.15": [
      ["Fahrzeugregeln", "Requisiten, Anhänger oder beliebige Autos sperren und Spawn-Spam stoppen. Mod-Autos, die so schwer sind, dass alle ruckeln, werden automatisch erkannt."],
      ["Server-Plugins", "Community-Spielmodi wie CareerMP, freeRoamMP und BeamJoy direkt von der Seite des jeweiligen Autors installieren."],
      ["Als Team betreiben", "Lade Freunde mit einem Link ein, der einmal funktioniert und nach einer Stunde abläuft, und bestimme pro Server, was jeder darf. Anmeldung auch mit Discord."],
    ],
  },
  notFound: {
    title: "Seite nicht gefunden - BeamMP EasyServer",
    h1: "404: falsch abgebogen",
    joke: "Diese Seite ist härter gecrasht als ein BeamNG-Auto bei Vollgas, und für sie gibt es keinen Reset-Knopf.",
    text: "Wenn du schon mal hier bist: Schau, wie weit du kommst.",
    start: "Drück die Leertaste oder tippe auf die Straße, um loszufahren",
    again: "Gecrasht! Leertaste drücken oder tippen, um es nochmal zu versuchen",
    best: "Rekord",
    gameLabel: "Minispiel: ein Auto springt über Pylonen und Reifen",
    home: "Zur Startseite",
    help: "Hilfe & FAQ",
  },
};
