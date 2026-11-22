// Website text in Hungarian. Same structure as en.js; anything left out shows in English.
export default {
  meta: {
    home: {
      title: "BeamMP EasyServer - saját BeamNG.drive multiplayer szerver egy kattintással",
      description: "Ingyenes egykattintásos telepítő és webes vezérlőpult BeamMP (BeamNG.drive multiplayer) szerverekhez Windowsra és Linuxra. Vírusellenőrzött modok, játékosstatisztika, moderálás, Discord, telefonos app.",
      ogTitle: "BeamMP EasyServer",
      ogDescription: "Saját BeamNG.drive multiplayer szerver egy kattintással - és irányíthatod a telefonodról.",
    },
    features: {
      title: "Funkciók - BeamMP EasyServer",
      description: "Mit tud a BeamMP EasyServer: vezetett telepítés, telefonról is használható vezérlőpult, vírusellenőrzött modok, járműszabályok, szerverpluginek és csapatfiókok. Ingyenes Windowsra és Linuxra.",
      ogTitle: "BeamMP EasyServer - funkciók",
      ogDescription: "Indíts BeamMP szervert a barátaidnak konfigurációs fájlok szerkesztése nélkül.",
    },
    help: {
      title: "Súgó és közösség - BeamMP EasyServer",
      description: "Válaszok a leggyakoribb BeamMP EasyServer kérdésekre: a barátok nem tudnak csatlakozni, porttovábbítás, modok, lassú csatlakozás, elfelejtett jelszó, Discord bot, összeomlások. Ha a tiéd nincs itt, kérdezd a közösséget.",
      ogTitle: "BeamMP EasyServer - Súgó és közösség",
      ogDescription: "Gyakori kérdések kész válaszokkal, és egy közösségi fórum minden másra.",
    },
  },

  nav: {
    start: "Kezdés", what: "Mit tud", downloads: "Letöltések", faq: "GYIK",
    features: "Funkciók", help: "Súgó", language: "Nyelv",
  },

  common: {
    download: "Letöltés",
    copy: "Másolás", copied: "Másolva", pressCtrlC: "Nyomd meg: Ctrl+C",
    license: "MIT licenc. Nem a BeamMP csapat vagy a BeamNG GmbH készítette, és nem kapcsolódik hozzájuk. Az EasyServer az ő munkájukra és sok mod- és pluginszerző munkájára épül: [a közreműködők]({GH}#-credits).",
    tryTitle: "Próbáld ki a gépeden",
    viewOnGithub: "Megnézem a GitHubon",
  },

  tour: {
    label: "A vezérlőpult oldalai",
    tabs: ["Áttekintés", "Modok", "Játékosok", "Állapotoldal"],
    alts: [
      "Az EasyServer vezérlőpult: a szerver fut, 16-ból 7 játékos online, pálya, üzemidő és hogy ki van fent",
      "A Modok oldal a vírusellenőrzés eredményeivel és a 380 MB-ot spóroló könnyű móddal",
      "Játékosstatisztika: játékosok naponta, a legforgalmasabb órák és a heti áttekintés",
      "Nyilvános állapotoldal 30 napos rendelkezésre állással",
    ],
  },

  home: {
    h1: "Saját BeamNG.drive multiplayer szerver, egy kattintással beállítva",
    lead: "Az EasyServer feltelepíti a hivatalos BeamMP szervert, és ad hozzá egy vezérlőpultot a gépedre vagy a telefonodra. Adj hozzá modokat, nézd meg, ki játszik, és tartsd távol a trollokat - konfigurációs fájlok és parancssor nélkül. Ingyenes és nyílt forráskódú, Windowsra és Linuxra.",
    how: "Hogyan működik",

    startTitle: "Kezdés",
    startSub: "Kb. tíz perc, nagyrészt a letöltésekre vársz.",
    stepsLabel: "Telepítési lépések",
    back: "Vissza",
    next: "Tovább:",
    steps: [
      { short: "AuthKey", title: "Szerezz egy ingyenes AuthKeyt",
        text: ["Lépj be a [keymaster.beammp.com](https://keymaster.beammp.com) oldalon Discorddal, kattints a **Keys**, majd a **+** gombra, és másold ki a kulcsot. Ettől lesz fent a szervered a nyilvános BeamMP listán."] },
      { short: "Telepítés", title: "Telepítés",
        text: ["Ez a tesztelt **Stable** verziót telepíti. A legújabb funkciókért nézd meg a [Rolling](#versions) verziót."] },
      { short: "Vezérlőpult", title: "Nyisd meg a vezérlőpultot",
        text: ["A szervergépen nyisd meg a **http://localhost:30815** címet, és válassz jelszót. Telefonról vagy egy másik otthoni gépről a **http://<szerver-ip>:30815** címet használd."] },
      { short: "Barátok", title: "Engedd be a barátaidat",
        text: ["Az **Állapot** oldalon kattints a **Port megnyitása automatikusan** gombra. A legtöbb router elfogadja. Ha a tiéd nem, továbbítsd te a 30814-es portot (TCP és UDP), és az Állapot oldal szól, ha működik.",
          "Utána kattints a **Meghívó másolása** gombra, és illeszd be Discordon. [Lépésről lépésre útmutatók]({GH}#-guides) (angolul)"] },
    ],
    osLabel: "A rendszered",
    windows: "Windows", linux: "Linux",
    winInstall: "Töltsd le a **BeamMP-EasyServer-Windows.zip** fájlt a [legújabb kiadásból]({LATEST}), csomagold ki, és kattints duplán az **Install-BeamMP-Server.bat** fájlra.",
    linuxInstall: "Illeszd be ezt egy terminálba:",
    videoTitle: "BeamMP szerver 5 perc alatt - telepítési videó (angolul)",
    videoNote: "Inkább megnéznéd? Az egész telepítés kb. 2 perc. [Megnyitás YouTube-on](https://youtu.be/DWD9HcW1OIc)",

    whatTitle: "Mit tud",
    whatSub: "Azoknak készült, akik a barátaikkal akarnak játszani, nem szerveradminisztrációt tanulni. [Minden funkció](features.html)",
    featuresLabel: "Funkciók",
    features: [
      { title: "Modok aggódás nélkül",
        alt: "A Modok oldal a vírusellenőrzés eredményeivel és a 380 MB-ot spóroló könnyű móddal",
        text: "Húzd a mod zip fájlokat az oldalra. Mindegyiket átnézi rejtett programok, álcázott fájlok és zipbombák után a Microsoft Defender vagy a ClamAV, ha szeretnéd, a VirusTotal is, mielőtt a játékosok letölthetnék.",
        list: ["**Modböngésző:** egy kattintással telepíts a BeamNG tárolóból, és ugyanígy frissíts",
          "**Könnyű mód:** a játékosok csak az épp játszott pályát töltik le, így gyorsabb a csatlakozás",
          "**Modcsomagok:** az összes modod egyetlen fájlként viheted át vagy oszthatod meg"] },
      { title: "Lásd, ki játszik, és mikor",
        alt: "Játékosstatisztika: játékosok naponta, a legforgalmasabb órák és a heti áttekintés",
        text: "Játékosok naponta, a legforgalmasabb órák, heti hőtérkép, legaktívabb játékosok, szerverrekordok és azok a pályák, amiken tényleg maradnak az emberek.",
        list: ["**Kirúgás, némítás és kitiltás** a vezérlőpultból, Discordból vagy a játék chatjéből",
          "**Karbantartási mód** bezárja a szervert, amíg dolgozol rajta",
          "**Csapatfiókok** a segítő barátoknak, csak azokkal a jogokkal, amiket te adsz"] },
      { title: "Döntsd el, mennyire legyen nyitott",
        alt: "Biztonsági előbeállítások: Legbiztonságosabb, Nyilvános, de biztonságos, Csak barátok, Mindenkinek nyitott, Gyenge gép",
        text: "Egy kattintás bárhová állítja a szervered a **Legbiztonságosabb** (csak meghívóval, antibot, elárasztás elleni védelem) és a **Mindenkinek nyitott** között. Minden konfigurációs változás mentődik, így látod, mi változott, és vissza is vonhatod.",
        list: ["**Meghívólista,** mert a BeamMP-ben nincs csatlakozási jelszó",
          "**Antibot:** csatlakozási kódok, vendégek tiltása és kapcsolatkorlátok"] },
      { title: "Irányítsd a telefonodról",
        alt: "A vezérlőpult telefonon",
        text: "A vezérlőpult bármilyen telefonos böngészőben működik. Van Android app, iPhone-on pedig a kezdőképernyőre teheted.",
        list: ["**Értesítések** összeomlásról, csatlakozásokról és frissítésekről telefonon, Discordon, Telegramon, Slacken vagy e-mailben",
          "**Discord bot** /status, /start, /restart, /whitelist parancsokkal és chathíddal",
          "**Alvás és Wake-on-LAN,** hogy ne kelljen egész nap mennie a gépnek"] },
      { title: "Állapotoldal a játékosoknak",
        alt: "Nyilvános állapotoldal 30 napos rendelkezésre állással",
        text: "Egy link megmutatja, fut-e a szerver, ki van fent, milyen modokat kell letölteni és mi a következő esemény. Bejelentkezés nélkül, címek és beállítások nélkül." },
    ],

    newTitle: "Újdonságok az 1.15-ben",
    newSub: "Már a Rollingban. Tesztelés után kerülnek a Stable-be.",
    news: [
      ["Járműszabályok", "Tilts le kellékeket, utánfutókat vagy bármilyen autót, és állítsd le a spawnspamet. A mindenkit lagoltató nehéz mod autókat magától kiszúrja."],
      ["Szerverpluginek", "Telepíts közösségi játékmódokat, például CareerMP-t, freeRoamMP-t és BeamJoyt, egyenesen a szerzőjük oldaláról."],
      ["Csapatban üzemeltetve", "Hívd meg a barátaidat egy linkkel, ami egyszer működik és egy óra múlva lejár, és döntsd el, ki mit csinálhat az egyes szervereken. Discorddal is beléphetnek."],
    ],

    alsoTitle: "Ez is benne van",
    alsoSub: "Mind opcionális. Kapcsold be, amire szükséged van.",
    also: [
      ["Meghívó másolása", "Kész Discord üzenet a címmel és a porttal."],
      ["Pályaszavazás és -rotáció", "A játékosok beírják: /vote, vagy a pálya menetrend szerint vált."],
      ["Heti események", "A „péntek esti drift” pályát és modokat vált, és bejelenti Discordon."],
      ["/tp és /repair", "Teleportálás a barátokhoz, ha elfogadják, valósághű vagy hardcore javítási szabályokkal."],
      ["Autótakarítás", "Az elhagyott autók eltűnnek, visszaszámlálással az éjszakai takarítás előtt."],
      ["Chateszközök", "Üdvözlő üzenet, időzített bejelentések, chatszűrő, antispam és /countdown."],
      ["Több szerver", "Egy gépen több szerver, mindegyik saját CPU-, RAM- és letöltési korláttal."],
      ["Éjszakai mentések", "Visszaállítás vagy költözés új gépre egyetlen fájllal."],
      ["IP-cím elrejtése", "Opcionális továbbító és elárasztás elleni védelem DDoS ellen."],
      ["Naplómagyarázó", "Szerverhibák érthető nyelven, azzal együtt, mit kell tenni."],
    ],

    secTitle: "Biztonság",
    secSub: "A szervered egy gép az otthoni hálózatodon, úgyhogy ez fontos.",
    security: [
      ["A kulcsok titkosítva vannak", "Az AuthKey, a tokenek és a jelszavak sosem kerülnek tárolásra sima szövegként."],
      ["Külön felhasználók Linuxon", "A játékszerver és a vezérlőpult is saját, korlátozott felhasználóként fut."],
      ["Kétlépcsős bejelentkezés", "Kötelező, mielőtt a vezérlőpult elérhető lenne az internetről."],
      ["Minden változtatásnál tesztelve", "Automatikus tesztek próbálnak betörni minden vezérlőpult-oldalra és a játékpluginba minden frissítésnél."],
    ],

    dlTitle: "Letöltések",
    dlSub: "Mindkettő ingyenes. Nem tudod, melyik? Válaszd a Stable-t.",
    stable: "Stable",
    stableWhat: "Tesztelt. Ez a GitHubon „Latest” jelölésű kiadás.",
    stableWin: "**Windows:** töltsd le a **BeamMP-EasyServer-Windows.zip** fájlt, csomagold ki, és kattints duplán az **Install-BeamMP-Server.bat** fájlra",
    linuxLabel: "**Linux:**",
    stableButton: "Stable letöltése",
    rolling: "Rolling",
    rollingWhat: "Új funkciók, amint elkészülnek. Lehetnek benne hibák.",
    rollingWin: "**Windows:** töltsd le a ZIP-et, csomagold ki, nyisd meg a **windows** mappát, és kattints duplán az **Install-BeamMP-Server.bat** fájlra",
    mac: "**Mac (kísérleti, csak Rolling):** illeszd be ezt a Terminálba. A szervert egy kis Linux virtuális gépben futtatja, ami a Mackel együtt indul ([hogyan működik]({GH}#mac-experimental)).",
    broken: "Valami elromlott? Telepítsd fölé a Stable-t. A beállításaid és a modjaid megmaradnak.",
    rollingButton: "Rolling letöltése (ZIP)",
    changes: "Mi változott az egyes verziókban: [változásnapló]({GH}/blob/main/CHANGELOG.md), [összes kiadás]({GH}/releases)",

    faqTitle: "Kérdések",
    faqSub: "[További válaszok és a közösség](help.html)",
    faq: [
      ["Ingyenes?", "Igen. Ingyenes és nyílt forráskódú (MIT licenc), minden funkcióval és reklámok nélkül. A BeamMP és a szervere is ingyenes. A játékhoz kell a saját BeamNG.drive példányod."],
      ["Ez a hivatalos BeamMP szerver?", "Az EasyServer a **hivatalos** BeamMP szervert telepíti, és naprakészen tartja. Maga az EasyServer közösségi projekt, nem a BeamMP csapat készítette vagy támogatja."],
      ["Milyen gép kell hozzá?", "Bármilyen 64 bites Windows 10 vagy 11 rendszerű PC, vagy Linux (Ubuntu, Linux Mint, Debian és mások, akár egy Raspberry Pi 4 vagy 5 64 bites rendszerrel). Egy baráti társaságnak egy régi laptop is elég. A feltöltési sebesség többet számít, mint a processzor."],
      ["Átállítja a routeremet?", "Csak ha a **Port megnyitása automatikusan** gombra kattintasz, ami megkéri a routert, hogy nyissa meg a játék portját. Különben csak a gép saját tűzfalán nyitja meg a portot, és előtte rákérdez."],
      ["Használhatom telefonról?", "Igen. A vezérlőpult bármilyen telefonos böngészőben működik, van Android app, és iPhone-on a kezdőképernyőre teheted. Otthonon kívülről is kezelheted, ha bekapcsolod a HTTPS-t és a kétlépcsős bejelentkezést."],
      ["Hibát találtam, vagy van egy ötletem", "[Nyiss egy issue-t a GitHubon]({GH}/issues/new/choose). Biztonsági problémánál inkább a privát bejelentést használd."],
    ],

    closing: "Töltsd le, indítsd el, és kövesd a lépéseket. Ha elakadsz, a Súgó oldal és a közösség segít.",
    footnote: "A képernyőképeken egy bemutató szerver látható kitalált játékosokkal.",
  },

  features: {
    h1: "Indíts BeamMP szervert a barátaidnak, konfigurációs fájl nélkül",
    lead: "Az EasyServer feltelepíti a hivatalos BeamMP szervert, és ad egy oldalt, ahonnan irányíthatod. Ingyenes, nyílt forráskódú, és Windowson és Linuxon is megy.",
    howInstall: "Telepítés lépései",
    onPage: "Ezen az oldalon",
    online: "Elérhetővé tétel", onlineSub: "Ennél a résznél akad el a legtöbb ember.",
    onlineRows: [
      ["Vezetett telepítés", ["Illeszd be az AuthKeyt, és a telepítő ellenőrzi, hogy érvényes-e. Beállítja, hogy a szerver a géppel együtt induljon, és összeomlás után újraindítja."]],
      ["A port megnyitása", ["Egy kattintás megkéri a routert, hogy nyissa meg a 30814-es portot. Ha a routered ezt nem engedi, a Súgó oldal elmagyarázza, hogyan csináld kézzel."]],
      ["„Miért nem tud csatlakozni a barátom?”", ["Az Állapot oldal ellenőrzi az AuthKeyt, a portot, a tűzfalat, és hogy fent van-e a szervered a BeamMP listán, és megmondja, melyik a rossz."]],
      ["Régi laptopok is jók", ["A Gyenge gép előbeállítás kevesebb játékost és autót enged, és gyorsan eltakarítja az elhagyott autókat, így egy régi laptop is elvisz egy kis szervert."]],
    ],
    running: "Üzemeltetés", runningSub: "Az asztal mellől vagy a kanapéról.",
    playersAlt: "A Játékosok oldal az online játékosok listájával és kirúgás, némítás, kitiltás gombokkal",
    playersCap: "A Játékosok oldal",
    phoneAlt: "A vezérlőpult telefonon",
    phoneCap: "Ugyanez telefonon",
    runningRows: [
      ["Indítás, leállítás, pályaváltás", ["Listából válthatsz pályát a ServerConfig.toml szerkesztése helyett. Bármilyen böngészőben működik, telefonon is."]],
      ["Játékosok és kitiltások", ["Kirúgás, némítás és kitiltás a vezérlőpultból, Discordból vagy chatparanccsal. Van meghívólista és karbantartási mód is."]],
      ["Modok", ["Húzz egy zipet az oldalra, vagy válassz egyet a BeamNG tárolóból. Mindegyiket átnézi a vírusellenőrző, mielőtt a játékosok letöltenék.", "Oszd meg az egész modlistádat egy rövid kóddal, és egy barátod szervere ugyanazokat telepítheti."]],
      ["Mentések és értesítések", ["Mentsd és állítsd vissza a konfigurációt. Kapj üzenetet Discordon, e-mailben, Telegramon vagy telefonon, ha a szerver összeomlik."]],
    ],
    newTitle: "Újdonságok az 1.15-ben", newSub: "Már a Rolling verzióban. Tesztelés után kerülnek a Stable-be.",
    newRows: [
      ["Járműszabályok", ["Tilts le kellékeket, a hatalmas fizikás kellékeket, utánfutókat vagy bármilyen kiválasztott autót. A mindenkit lagoltató nehéz mod autókat magától kiszúrja.", "Van spawn-várakozási idő is, és előbeállítások verseny- és szerepjátékszerverekhez."]],
      ["Szerverpluginek", ["Telepíts közösségi játékmódokat, például CareerMP-t, freeRoamMP-t és BeamJoyt. A szerzőjük oldaláról töltődnek le, és telepítés előtt látod, melyik fájl hová kerül."]],
      ["Csapatban üzemeltetve", ["Küldj egy barátodnak meghívólinket, ami egyszer működik, és egy óra múlva lejár. Adj neki szerepet, például néző vagy moderátor, minden szerveren külön.", "Jelszó helyett Discorddal is beléphetnek. Aki az otthoni hálózatodon kívülről lép be, annak kétlépcsős bejelentkezési kód kell."]],
    ],
    closing: "Töltsd le, indítsd el, és kövesd a lépéseket. A legtöbben kb. öt perc alatt online vannak. Ha elakadsz, a Súgó oldal és a közösség segít.",
    footnote: "A Mac verzió kísérleti, és csak a Rollingban érhető el.",
  },

  help: {
    h1: "Súgó és közösség",
    lead: "A szerverüzemeltetők leggyakoribb kérdései válaszokkal. Nincs itt a tiéd? Kérdezz a közösségi fórumon.",
    search: "Keresés, pl. „barátok nem tudnak csatlakozni” vagy „modok”",
    searchLabel: "Kérdések keresése",
    topicsLabel: "Témák",
    all: "Mind",
    question: "kérdés", questions: "kérdés", match: "találat",
    results: "Találatok", marked: "Az egyező szavak ki vannak emelve.",
    mostAsked: "Leggyakoribb",
    copyLink: "Link másolása ehhez a válaszhoz", linkCopied: "Link másolva",
    empty: "Erre még nincs válasz. [Kérdezd meg a fórumon]({ASK}), és lehet, hogy ide is bekerül.",
    askTitle: "Nem találtad a választ?",
    askText: "Kérdezd a közösséget. Keress régi témákban, ossz meg ötleteket, vagy mutasd meg a szervered. Csak egy ingyenes GitHub fiók kell.",
    askButton: "Kérdés feltevése",
    forumButton: "Fórum megnyitása",
    cats: {
      start: "Első lépések", join: "Csatlakozás és hálózat", mods: "Modok és pályák",
      dash: "Vezérlőpult és belépés", discord: "Discord és értesítések", trouble: "Problémák",
    },
    qa: [
      ["what-do-i-need", "start", "Mi kell egy szerver üzemeltetéséhez?", [
        { ul: ["Egy gép, ami bekapcsolva marad, amíg játszotok: bármilyen 64 bites Windows 10/11 rendszerű PC, vagy Linux (Ubuntu, Linux Mint, Debian, akár egy Raspberry Pi 4/5 64 bites rendszerrel). Egy baráti társaságnak egy régi laptop is jó.",
          "Egy ingyenes BeamMP **AuthKey** (lásd a következő kérdést).",
          "A saját BeamNG.drive példányod a játékhoz. Maga a szerver ingyenes."] },
        "A feltöltési sebesség többet számít, mint a processzor: minden játékos tőled tölti le a modokat."]],
      ["authkey", "start", "Honnan szerzek AuthKeyt?", [
        { ol: ["Menj a [keymaster.beammp.com](https://keymaster.beammp.com) oldalra, és lépj be Discorddal.",
          "Kattints a **Keys**, majd a **+** gombra, és adj neki bármilyen nevet.",
          "Másold ki a kulcsot, és illeszd be a telepítőbe, vagy később a **Konfiguráció → AuthKey** résznél."] },
        "Kulcs nélkül is működik a szerver az otthoni hálózatodon, csak nem lesz fent a nyilvános listán. Nyilvános szerverenként egy kulcs kell."]],
      ["windows-or-linux", "start", "Windowst vagy Linuxot válasszak?", [
        "**Ugyanazon a gépen játszol, amin a szerver fut?** A Windows a legegyszerűbb: töltsd le a zipet, és kattints duplán az **Install-BeamMP-Server.bat** fájlra.",
        "**Külön gép csak a szervernek?** A Linux jobb. A szerver a háttérben fut, a gép indulásakor magától elindul, összeomlás után újraindul, és **laptop módban** lecsukott fedéllel is megy. Egy parancs mindent feltelepít."]],
      ["update", "start", "Hogyan frissítem az EasyServert és a BeamMP szervert?", [
        { ul: ["**Maga az EasyServer:** a vezérlőpult **Frissítések** oldalán. Windowson a régi fölé is futtathatod a legújabb telepítőt; a beállításaid megmaradnak.",
          "**A BeamMP szerver:** a **Konfiguráció → Újraindítások és frissítések → BeamMP frissítések telepítése** automatikusan frissíti az ütemezett újraindításkor. Kézzel: `beammp update` Linuxon, **Update-BeamMP-Server.bat** Windowson."] }]],

      ["not-in-server-list", "join", "A szerverem nem jelenik meg a BeamMP szerverlistán", [
        { ol: ["A **Konfiguráció → AuthKey** legyen kitöltve.",
          "A **Konfiguráció → Privát** legyen kikapcsolva. A „Legbiztonságosabb” és a „Csak barátok” előbeállítás szándékosan elrejti a szervert.",
          "A port legyen elérhető az internetről (lásd a következő kérdést).",
          "Indítás után adj neki egy-két percet."] },
        "Az **Állapot → Ellenőrzés újra** mindezt ellenőrzi, és megmondja, melyik a rossz."]],
      ["friends-cant-join", "join", "A Wi-Fi-men lévő barátok be tudnak jönni, a házon kívüliek nem", [
        "A routerednek be kell engednie őket. Ezt csak egyszer kell beállítani:",
        { ol: ["A routerben adj fix címet a szervergépnek (gyakran *DHCP-foglalás* vagy *statikus IP* a neve).",
          "**Továbbítsd a 30814-es portot, TCP-t és UDP-t**, erre a gépre. Keress rá: „*a routered típusa* porttovábbítás”, hogy megtaláld a pontos menüt.",
          "A vezérlőpultban: **Állapot → Teljes ellenőrzés**. Az „Elérhető az internetről” legyen zöld."] },
        "Még mindig piros? Egyes szolgáltatók egy címen osztoznak sok háztartás között (CGNAT), ilyenkor a porttovábbítás nem működhet. Az Állapot oldal szól, ha ez a helyzet: kérj publikus IPv4 címet a szolgáltatódtól, vagy használj továbbítót (**Beállítások → IP-cím elrejtése**)."], true],
      ["one-player-cant-join", "join", "Egy bizonyos játékos nem tud csatlakozni", [
        "**Állapot → Valaki nem tud csatlakozni?** → írd be a BeamMP nevét → **Ellenőrzés**. Kiolvassa az utolsó próbálkozását, és megmondja, miért nem sikerült: kitiltva, nincs a meghívólistán, karbantartás, vendégek tiltva, antibot kód, túl sok játékos egy kapcsolatról, tele a szerver stb., a megoldással együtt.",
        "Az elutasított játékosok a **Konfiguráció → Ki csatlakozhat → Nemrég elutasítva** résznél is megjelennek egy **+ engedélyezés** gombbal."]],
      ["password", "join", "Hogyan teszek jelszót a szerverre / hogyan lesz csak a barátoké?", [
        "A BeamMP-ben nincs csatlakozási jelszó, ezért az EasyServer **meghívólistát** használ helyette:",
        { ol: ["**Konfiguráció → Ki csatlakozhat**: kapcsold be a listát, és írd be a barátaid BeamMP nevét, soronként egyet.",
          "**Lista mentése**. Azonnal érvényes, újraindítás nélkül."] },
        "Mindenki más „csak meghívóval” üzenetet kap. A leggyorsabb a **Legbiztonságosabb** vagy a **Csak barátok** előbeállítás a **Konfiguráció → Biztonsági előbeállítások** résznél. A Discord bottal: `/whitelist add név`."]],
      ["ip-changes", "join", "Folyton változik az otthoni IP-címem", [
        "Állíts be egy ingyenes fix nevet: **Beállítások → Fix cím (DuckDNS)**. A barátaid ezután a `nevem.duckdns.org` címre csatlakoznak, és ez akkor is működik, ha a cím változik. Nyilvános szervereknek erre nincs szükségük: a szerverlistán mindig az aktuális cím van."]],
      ["hide-ip", "join", "Látják a játékosok az otthoni IP-címemet? Mi a helyzet a DDoS-sal?", [
        "A játékosok a szerveredhez csatlakoznak, szóval igen, ki tudják deríteni a címet, mint bármelyik otthon futtatott játékszervernél. Ha ez zavar, a **Beállítások → IP-cím elrejtése** egy továbbítón keresztül vezeti a játékosokat, az elárasztás elleni védelem pedig benne van a **Legbiztonságosabb** és a **Nyilvános, de biztonságos** előbeállításban. Lásd: [Védd az IP-címed]({GH}/blob/main/PROTECT-YOUR-IP.md) (angolul)."]],

      ["add-mods", "mods", "Hogyan adok hozzá modokat?", [
        { ol: ["Nyisd meg a vezérlőpultban a **Modok** oldalt, és húzd rá a mod **.zip** fájlokat.",
          "Mindegyiket először átnézi a vírusellenőrző. Kb. 15 másodperc múlva újraindul a szerver (Windowson nyomd meg az Újraindítás gombot). Ez lecsatlakoztatja a játékosokat, úgyhogy akkor adj hozzá modot, amikor csend van.",
          "A pályamodok **map:** címkét kapnak. Kattints a **Pálya használata** gombra a játékhoz."] },
        "A játékosoknak nem kell semmit telepíteniük: a BeamMP csatlakozáskor letölti nekik a modokat. Más módok is vannak: a **Drop BeamMP Mods Here** asztali ikon (Windows), a `BeamMP-Mods` mappa vagy a `beammp addmod fájl.zip` (Linux)."]],
      ["slow-joining", "mods", "A csatlakozás örökké tart a modletöltés miatt", [
        { ul: ["Kapcsold be a **könnyű módot** a Modok oldalon: a játékosok csak az épp játszott pályát töltik le. A többi pályamod magától visszajön, ha az ő pályájukra váltasz.",
          "Töröld a modokat, amiket senki nem használ. A Modok oldal tetején lévő kártya mutatja a teljes letöltést.",
          "A lassú netű barátok kaphatnak egy **modcsomagot** (Modok → Modcsomag), és csatlakozás előtt bemásolhatják a fájlokat a `Documents\\BeamNG.drive\\mods\\multiplayer` mappába."] },
        "Itt a feltöltési sebességed a korlát, úgyhogy egy nagy modcsomag bármilyen otthoni neten lassú."]],
      ["mod-blocked", "mods", "A vírusellenőrző letiltott egy modot. Tényleg veszélyes?", [
        "Az EasyServer letiltja azokat a modokat, amikben programok, álcázott fájlok vagy zipbombák vannak, vagy amiket a Microsoft Defender, a ClamAV vagy a VirusTotal megjelöl. Egy normál BeamNG mod csak autó-, pálya- és szkriptfájlokból áll, tehát egy letiltott modban olyasmi van, aminek nem kéne. Az ok ott van mellette.",
        "A letiltott fájlok sosem jutnak el a szerverre vagy a játékosaidhoz. Töltsd le újra a modot a hivatalos BeamNG tárolóból egy újrafeltöltős oldal helyett."]],
      ["change-map", "mods", "Hogyan váltok pályát, vagy hagyom, hogy a játékosok szavazzanak?", [
        { ul: ["**Most:** **Áttekintés → Pálya**, válassz egyet, erősítsd meg. A szerver az új pályán indul újra.",
          "**Szavazás:** **Konfiguráció → Pályaszavazás**, jelöld be az engedélyezett pályákat. A játékosok beírják a játék chatjébe: `/vote`.",
          "**Automatikusan:** **Konfiguráció → Pályarotáció** (1-24 óránként) vagy **Konfiguráció → Események** („péntek esti drift”)."] }]],

      ["forgot-password", "dash", "Elfelejtettem a vezérlőpult jelszavát / elveszett a telefonom a kétlépcsős belépéshez", [
        { ul: ["**Windows:** kattints duplán a **Reset-Dashboard-Login.bat** fájlra az EasyServer mappában.",
          "**Linux:** `sudo beammp reset-login`"] },
        "Utána nyisd meg a vezérlőpultot **a szervergépen**, és válassz új jelszót. A kétlépcsős belépés kikapcsol, úgyhogy állítsd be újra az új telefonoddal."]],
      ["connection-reset", "dash", "A böngésző azt írja: „a kapcsolat alaphelyzetbe állt” vagy „nem biztonságos”", [
        "**„A kapcsolat alaphelyzetbe állt”:** be van kapcsolva a HTTPS, de `http://` címet nyitottál meg. Használd a `https://` címet, vagy frissíts 1.12.1-re vagy újabbra, ami magától átirányít.",
        "**„Nem biztonságos” / tanúsítványfigyelmeztetés:** első alkalommal normális. A vezérlőpult saját tanúsítványt készít, ezért a böngésző még nem ismeri. Hasonlítsd össze a **Beállítások** alatt látható ujjlenyomatot a böngésző figyelmeztetésében lévővel, aztán folytasd. Az Android app megjegyzi helyetted."]],
      ["phone", "dash", "Kezelhetem a szervert telefonról, vagy otthonon kívülről?", [
        "**Otthon:** nyisd meg a `http://<szerver-ip>:30815` címet a telefonodon, vagy telepítsd az Android appot (**BeamMP-EasyServer.apk** a [legújabb kiadásból]({LATEST})), és olvasd be a QR-kódot a **Beállítások → Telefonos app** résznél. iPhone: Safari → Megosztás → Főképernyőhöz adás.",
        "**Bárhonnan:** kapcsold be a HTTPS-t és a kétlépcsős belépést, használj legalább 12 karakteres jelszót, aztán **Beállítások → Elérés az internetről**, és továbbítsd a **30815-ös (TCP)** portot."]],
      ["stay-logged-in", "dash", "Megjegyezheti a jelszavam, hogy ne kelljen mindig belépnem?", [
        "Igen (1.12.1-es verziótól). Kapcsold be a **Maradjak bejelentkezve ezen az eszközön** opciót a belépő oldalon. Az az eszköz ezután az utolsó látogatástól számított 30 napig magától belép, újraindítás után is. A böngésződ jelszókezelője is felajánlja a jelszó mentését.",
        "Elveszett egy telefon? **Beállítások → Megjegyzett eszközök → Elfelejtés**."]],
      ["team", "dash", "Hogyan adhatok hozzáférést barátoknak a moderáláshoz?", [
        "**Beállítások → Felhasználók és szerepek**: név, szerep, jelszó → **Hozzáadás**.",
        { ul: ["**Néző**: nézelődhet, nem változtathat semmit", "**Moderátor**: kirúgás, némítás, kitiltás, meghívólista, újraindítás, karbantartás", "**Admin**: minden, kivéve a felhasználókat, a jelszavakat és az internetes elérést"] },
        "Ha csak játékon belül moderálnának, add hozzá a BeamMP nevüket a **Konfiguráció → Moderáció és antibot → Adminok** résznél. Ezután használhatják a `/kick`, `/ban` és `/mute` parancsot a játék chatjében."]],

      ["discord-bot", "discord", "Hogyan állítom be a Discord botot?", [
        { ol: ["[discord.com/developers/applications](https://discord.com/developers/applications) → **New Application**.",
          "**Installation** → Install Link: **None** → mentés.",
          "**Bot** → kapcsold ki a **Public Bot**, és kapcsold be a **Message Content Intent** opciót (a chathídhoz) → **Reset Token** → másolás.",
          "Vezérlőpult: **Beállítások → Discord bot** → illeszd be a tokent, kapcsold be, **Mentés**. Ha **Online** lesz, kattints a **Bot hozzáadása a Discordodhoz** gombra.",
          "Írd be Discordon: `/status`."] },
        "A bot tokenjét soha ne add ki senkinek. Ha mégis kiszivárog, nyomd meg újra a Reset Token gombot."]],
      ["slash-commands", "discord", "A bot online, de nem jelennek meg a perjeles parancsok", [
        { ul: ["Az új parancsok megjelenése eltarthat egy percig. Indítsd újra a Discordot (PC-n Ctrl+R).",
          "Ellenőrizd, hogy a **Beállítások → Discord bot** résznél a te Discord szervered van-e beállítva, ahol a bot válaszol.",
          "A `/start`, `/stop`, `/restart` és `/whitelist` csak a **Szerver kezelése** joggal rendelkezőknek vagy az általad engedélyezett Discord felhasználóknak jelenik meg."] }]],
      ["alerts", "discord", "Kaphatok értesítést, ha összeomlik a szerver vagy valaki csatlakozik?", [
        "Igen, telefonon (ingyenes **ntfy** app, **Beállítások → Telefonos app**), Discordon, Telegramon, Slacken és más appokban, vagy e-mailben. Azt, hogy miről kapsz hírt, az **Értesíts, ha** résznél választhatod ki. A **Konfiguráció → Csatlakozási értesítések** jelez, ha kiválasztott játékosok csatlakoznak."]],

      ["crash-lag", "trouble", "A szerver folyton összeomlik vagy laggol", [
        { ol: ["A **Naplók → A teljes napló magyarázata** érthető nyelven felsorol minden hibát, a hibás modokat és a memóriahiányt is.",
          "Az **Állapot** mutatja a memóriát és a lemezt, a **Beállítások → A gép terhelése** pedig 24 órás grafikonokat ad.",
          "Régebbi gépen használd a **Gyenge gép** előbeállítást, csökkentsd a maximális autószámot, és kapcsold be a könnyű módot."] },
        "Az összeomlott szerver magától újraindul, és szól is, ha be vannak kapcsolva az összeomlási értesítések."]],
      ["undo", "trouble", "Átállítottam valamit, és most valami nem működik", [
        "A **Konfiguráció → Mi változott?** megőrzi a konfiguráció utolsó 40 verzióját, azzal együtt, ki mit változtatott. Az **Összehasonlítás a mostanival** mutatja a különbséget, a **Visszaállítás** pedig visszalép. Az AuthKey megmarad, és a visszavonást is visszavonhatod."]],
      ["sleep", "trouble", "Éjjel-nappal mennie kell a gépnek?", [
        "Nem. A **Beállítások → Alvás és ébresztés** elaltatja, ha egy ideje senki nem játszott, és események előtt felébreszti. **Wake-on-LAN**-nal (hálózati kábel kell) a barátaid is felébreszthetik a `/start` paranccsal Discordon vagy az appban az **Ébresztés** gombbal. A kompatibilitási pontszám megmutatja, mit kell még beállítani."]],
      ["new-computer", "trouble", "Hogyan költöztetem a szerveremet új gépre?", [
        { ol: ["Régi gép: **Beállítások → Mentés / költözés másik gépre → Beállítások + modok exportálása**.",
          "Telepítsd az EasyServert az újra, majd **Importálás…** azzal a fájllal.",
          "Illeszd be újra az AuthKeyt: kulcsok és jelszavak sosem kerülnek az exportba."] },
        "Az éjszakai mentések alapból be vannak kapcsolva, és az utolsó 7 bármikor letölthető."]],
      ["get-help", "trouble", "A problémám nincs itt. Hogyan kapok segítséget?", [
        { ol: ["**Állapot → Diagnosztikai jelentés letöltése**. A kulcsok, jelszavak és címek kikerülnek belőle.",
          "[Kérdezz a közösségi fórumon]({ASK}), és csatold a jelentést. A hibák az [issue-k]({GH}/issues/new/choose) közé valók."] },
        "Biztonsági problémát találtál? Kérlek, a [privát bejelentést]({GH}/security/advisories/new) használd, ne tedd közzé nyilvánosan."]],
    ],
  },
};
