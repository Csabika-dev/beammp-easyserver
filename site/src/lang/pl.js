// Website text in Polish. Same structure as en.js; anything left out shows in English.
export default {
  meta: {
    home: {
      title: "BeamMP EasyServer - własny serwer multiplayer BeamNG.drive jednym kliknięciem",
      description: "Darmowy instalator jednym kliknięciem i panel w przeglądarce dla serwerów BeamMP (multiplayer BeamNG.drive) na Windows i Linux. Mody ze skanem antywirusowym, statystyki graczy, moderacja, Discord, aplikacja na telefon.",
      ogTitle: "BeamMP EasyServer",
      ogDescription: "Postaw własny serwer multiplayer BeamNG.drive jednym kliknięciem i steruj nim z telefonu.",
    },
    features: {
      title: "Funkcje - BeamMP EasyServer",
      description: "Co potrafi BeamMP EasyServer: prowadzona instalacja, panel, z którego skorzystasz na telefonie, mody sprawdzane antywirusem, zasady pojazdów, pluginy serwera i konta zespołu. Za darmo na Windows i Linux.",
      ogTitle: "BeamMP EasyServer - funkcje",
      ogDescription: "Postaw serwer BeamMP dla znajomych bez edytowania plików konfiguracyjnych.",
    },
    help: {
      title: "Pomoc i społeczność - BeamMP EasyServer",
      description: "Odpowiedzi na najczęstsze pytania o BeamMP EasyServer: znajomi nie mogą dołączyć, przekierowanie portów, mody, wolne dołączanie, zapomniane hasło, bot Discord, awarie. Zapytaj społeczność, jeśli twojego pytania tu nie ma.",
      ogTitle: "BeamMP EasyServer - Pomoc i społeczność",
      ogDescription: "Częste pytania z gotowymi odpowiedziami i forum społeczności na całą resztę.",
    },
  },

  nav: {
    start: "Pierwsze kroki", what: "Co potrafi", downloads: "Pobieranie", faq: "FAQ",
    features: "Funkcje", help: "Pomoc", language: "Język",
  },

  common: {
    // "What's new": {v} is the version from CHANGELOG.md.
    newTitle: "Nowości w {v}", newRolling: "Już w Rolling. Trafią do Stable, gdy zostaną przetestowane.", newStable: "Już w wersji Stable.",
    download: "Pobierz",
    copy: "Kopiuj", copied: "Skopiowano", pressCtrlC: "Naciśnij Ctrl+C",
    license: "Licencja MIT. Nie jest tworzony przez zespół BeamMP ani BeamNG GmbH i nie jest z nimi powiązany. EasyServer opiera się na ich pracy oraz pracy wielu autorów modów i pluginów: [zobacz podziękowania]({GH}#-credits).",
    tryTitle: "Wypróbuj na swoim PC",
    viewOnGithub: "Zobacz na GitHubie",
    downloadFor: "Pobierz na {os}",
    downloadVFor: "Pobierz {v} na {os}",
    setupFor: "Zainstaluj na {os}",
    macRolling: "Mac: wersja Rolling (eksperymentalna)",
    onPhone: "Pobierz na komputer",
    otherSystems: "Inne systemy i wersje",
    themeDark: "Włącz tryb ciemny",
    themeLight: "Włącz tryb jasny",
  },

  tour: {
    label: "Strony panelu",
    tabs: ["Przegląd", "Mody", "Gracze", "Strona statusu"],
    alts: [
      "Panel EasyServer: serwer działa, 7 z 16 graczy online, mapa, czas działania i kto jest online",
      "Strona modów z wynikami skanu antywirusowego i trybem lekkim oszczędzającym 380 MB",
      "Statystyki graczy: gracze dziennie, najbardziej oblegane godziny i przegląd tygodnia",
      "Publiczna strona statusu z dostępnością z 30 dni",
    ],
  },

  home: {
    h1: "Twój własny serwer multiplayer BeamNG.drive, ustawiony jednym kliknięciem",
    lead: "EasyServer instaluje oficjalny serwer BeamMP i daje ci do niego panel na komputerze lub telefonie. Dodawaj mody, sprawdzaj, kto gra, i trzymaj trolli z daleka - bez plików konfiguracyjnych i wiersza poleceń. Za darmo i open source, na Windows i Linux.",
    how: "Jak to działa",

    startTitle: "Pierwsze kroki",
    startSub: "Około dziesięciu minut, głównie czekania na pobieranie.",
    stepsLabel: "Kroki instalacji",
    back: "Wstecz",
    next: "Dalej:",
    steps: [
      { short: "AuthKey", title: "Zdobądź darmowy AuthKey",
        text: ["Zaloguj się na [keymaster.beammp.com](https://keymaster.beammp.com) przez Discord, kliknij **Keys**, potem **+**, i skopiuj klucz. Dzięki niemu twój serwer pojawi się na publicznej liście BeamMP."] },
      { short: "Instalacja", title: "Instalacja",
        text: ["To instaluje przetestowaną wersję **Stable**. Najnowsze funkcje znajdziesz w wersji [Rolling](#versions)."] },
      { short: "Panel", title: "Otwórz panel",
        text: ["Na komputerze z serwerem wejdź na **http://localhost:30815** i wybierz hasło. Z telefonu albo innego komputera w domu użyj **http://<ip-serwera>:30815**."] },
      { short: "Znajomi", title: "Wpuść znajomych",
        text: ["Na stronie **Stan** kliknij **Otwórz port automatycznie**. Większość routerów to przyjmuje. Jeśli twój nie, przekieruj port 30814 (TCP i UDP) samodzielnie, a strona Stan powie ci, kiedy działa.",
          "Potem kliknij **Kopiuj zaproszenie** i wklej je na Discordzie. [Poradniki krok po kroku]({GH}#-guides) (po angielsku)"] },
    ],
    osLabel: "Twój system",
    windows: "Windows", linux: "Linux",
    winInstall: "Pobierz **BeamMP-EasyServer-Windows.zip** z [najnowszego wydania]({LATEST}), rozpakuj i kliknij dwukrotnie **Install-BeamMP-Server.bat**.",
    linuxInstall: "Wklej to do terminala:",
    videoTitle: "Jak postawić serwer BeamMP w 5 minut - film instalacyjny (po angielsku)",
    videoPlay: "Odtwórz film instalacyjny (po angielsku)",
    videoConsent: "Ładuje się z YouTube, który wtedy widzi Twój adres IP.",
    videoNote: "Wolisz obejrzeć? Cała instalacja trwa około 2 minut. [Otwórz na YouTube](https://youtu.be/DWD9HcW1OIc)",

    whatTitle: "Co potrafi",
    whatSub: "Dla ludzi, którzy chcą grać ze znajomymi, a nie uczyć się administrowania serwerem. [Wszystkie funkcje](features.html)",
    featuresLabel: "Funkcje",
    features: [
      { title: "Mody bez obaw",
        alt: "Strona modów z wynikami skanu antywirusowego i trybem lekkim oszczędzającym 380 MB",
        text: "Przeciągnij pliki zip z modami na stronę. Każdy jest sprawdzany pod kątem ukrytych programów, zamaskowanych plików i bomb zip przez Microsoft Defender lub ClamAV, a na życzenie także VirusTotal, zanim gracze będą mogli go pobrać.",
        list: ["**Przeglądarka modów:** instaluj z repozytorium BeamNG jednym kliknięciem i tak samo aktualizuj",
          "**Tryb lekki:** gracze pobierają tylko aktualnie graną mapę, więc dołączanie jest szybsze",
          "**Paczki modów:** przenieś lub udostępnij wszystkie mody jako jeden plik"] },
      { title: "Zobacz, kto gra i kiedy",
        alt: "Statystyki graczy: gracze dziennie, najbardziej oblegane godziny i przegląd tygodnia",
        text: "Gracze dziennie, najbardziej oblegane godziny, tygodniowa mapa cieplna, najaktywniejsi gracze, rekordy serwera i mapy, na których ludzie naprawdę zostają.",
        list: ["**Wyrzucaj, wyciszaj i banuj** z panelu, Discorda lub czatu w grze",
          "**Tryb konserwacji** zamyka serwer, gdy nad nim pracujesz",
          "**Konta zespołu** dla pomagających znajomych, tylko z uprawnieniami, które im dasz"] },
      { title: "Zdecyduj, jak bardzo jest otwarty",
        alt: "Presety bezpieczeństwa: Najbezpieczniej, Publiczny, ale bezpieczny, Tylko znajomi, Otwarty dla wszystkich, Słaby komputer",
        text: "Jedno kliknięcie ustawia serwer gdziekolwiek między **Najbezpieczniej** (tylko z zaproszeniem, antybot, ochrona przed zalewaniem) a **Otwarty dla wszystkich**. Każda zmiana konfiguracji jest zapisywana, więc widzisz, co się zmieniło, i możesz to cofnąć.",
        list: ["**Lista zaproszonych,** bo BeamMP nie ma hasła do dołączania",
          "**Antybot:** kody dołączania, blokowanie gości i limity połączeń"] },
      { title: "Steruj z telefonu",
        alt: "Panel na telefonie",
        text: "Panel działa w każdej przeglądarce na telefonie. Jest aplikacja na Androida, a na iPhonie możesz dodać go do ekranu głównego.",
        list: ["**Powiadomienia** o awariach, dołączeniach i aktualizacjach na telefon, Discord, Telegram, Slack lub e-mail",
          "**Bot Discord** z /status, /start, /restart, /whitelist i mostem czatu",
          "**Usypianie i Wake-on-LAN,** żeby komputer nie musiał chodzić cały dzień"] },
      { title: "Strona statusu dla graczy",
        alt: "Publiczna strona statusu z dostępnością z 30 dni",
        text: "Jeden link pokazuje, czy serwer działa, kto jest online, które mody pobrać i jakie jest następne wydarzenie. Bez logowania i bez pokazywania adresów czy ustawień." },
    ],

    alsoTitle: "W zestawie także",
    alsoSub: "Wszystko opcjonalne. Włącz to, czego potrzebujesz.",
    also: [
      ["Kopiuj zaproszenie", "Gotowa wiadomość na Discorda z adresem i portem."],
      ["Głosowanie i rotacja map", "Gracze wpisują /vote albo mapa zmienia się według harmonogramu."],
      ["Cotygodniowe wydarzenia", "„Piątkowy wieczór driftu” zmienia mapę i mody i jest ogłaszany na Discordzie."],
      ["/tp i /repair", "Teleport do znajomych, gdy się zgodzą, z realistycznymi lub hardkorowymi zasadami naprawy."],
      ["Sprzątanie aut", "Porzucone auta są usuwane, z odliczaniem przed nocnym sprzątaniem."],
      ["Narzędzia czatu", "Wiadomość powitalna, ogłoszenia o stałych porach, filtr czatu, antyspam i /countdown."],
      ["Kilka serwerów", "Więcej niż jeden serwer na jednym PC, każdy z własnymi limitami CPU, RAM i pobierania."],
      ["Nocne kopie zapasowe", "Przywróć albo przenieś się na nowy komputer jednym plikiem."],
      ["Ukryj swoje IP", "Opcjonalny przekaźnik i ochrona przed zalewaniem przeciw DDoS."],
      ["Objaśniacz logów", "Błędy serwera prostym językiem, razem z tym, co z nimi zrobić."],
    ],

    secTitle: "Bezpieczeństwo",
    secSub: "Twój serwer to komputer w domowej sieci, więc to ważne.",
    security: [
      ["Klucze są szyfrowane", "Twój AuthKey, tokeny i hasła nigdy nie są zapisywane zwykłym tekstem."],
      ["Osobni użytkownicy na Linuksie", "Serwer gry i panel działają każdy jako osobny, ograniczony użytkownik."],
      ["Logowanie dwuetapowe", "Wymagane, zanim panel będzie dostępny z internetu."],
      ["Testowany przy każdej zmianie", "Automatyczne testy przy każdej aktualizacji próbują włamać się na każdą stronę panelu i do pluginu gry."],
    ],

    dlTitle: "Pobieranie",
    dlSub: "Obie wersje są darmowe. Nie wiesz którą? Weź Stable.",
    stable: "Stable",
    stableWhat: "Przetestowana. To wydanie oznaczone na GitHubie jako „Latest”.",
    stableWin: "**Windows:** pobierz **BeamMP-EasyServer-Windows.zip**, rozpakuj i kliknij dwukrotnie **Install-BeamMP-Server.bat**",
    linuxLabel: "**Linux:**",
    stableButton: "Pobierz Stable",
    rolling: "Rolling",
    rollingWhat: "Nowe funkcje od razu, gdy są gotowe. Może mieć błędy.",
    rollingWin: "**Windows:** pobierz ZIP, rozpakuj, otwórz folder **windows** i kliknij dwukrotnie **Install-BeamMP-Server.bat**",
    mac: "**Mac (eksperymentalnie, tylko Rolling):** wklej to do Terminala. Uruchamia serwer w małej maszynie wirtualnej z Linuksem, która startuje razem z Makiem ([jak to działa]({GH}#mac-experimental)).",
    broken: "Coś nie działa? Zainstaluj na to Stable. Ustawienia i mody zostaną.",
    rollingButton: "Pobierz Rolling (ZIP)",
    changes: "Co się zmieniło w każdej wersji: [lista zmian]({GH}/blob/main/CHANGELOG.md), [wszystkie wydania]({GH}/releases)",

    faqTitle: "Pytania",
    faqSub: "[Więcej odpowiedzi i społeczność](help.html)",
    faq: [
      ["Czy to jest darmowe?", "Tak. Jest darmowe i open source (licencja MIT), ze wszystkimi funkcjami i bez reklam. BeamMP i jego serwer też są darmowe. Do grania potrzebujesz własnej kopii BeamNG.drive."],
      ["Czy to oficjalny serwer BeamMP?", "EasyServer instaluje **oficjalny** serwer BeamMP i dba o jego aktualizacje. Sam EasyServer to projekt społeczności, nie jest tworzony ani wspierany przez zespół BeamMP."],
      ["Jakiego komputera potrzebuję?", "Dowolnego 64-bitowego PC z Windows 10 lub 11 albo Linuksa (Ubuntu, Linux Mint, Debian i inne, także Raspberry Pi 4 lub 5 z 64-bitowym systemem). Dla grupy znajomych wystarczy stary laptop. Prędkość wysyłania ma większe znaczenie niż procesor."],
      ["Czy zmienia coś w moim routerze?", "Tylko jeśli klikniesz **Otwórz port automatycznie**, co prosi router o otwarcie portu gry. W przeciwnym razie otwiera port tylko w zaporze samego komputera, i najpierw pyta."],
      ["Czy mogę korzystać z telefonu?", "Tak. Panel działa w każdej przeglądarce na telefonie, jest aplikacja na Androida, a na iPhonie możesz dodać go do ekranu głównego. Zarządzanie spoza domu działa, gdy włączysz HTTPS i logowanie dwuetapowe."],
      ["Znalazłem błąd albo mam pomysł", "[Zgłoś to na GitHubie]({GH}/issues/new/choose). Problemy z bezpieczeństwem zgłaszaj prywatnie."],
    ],

    closing: "Pobierz, uruchom i idź za krokami. Jeśli utkniesz, pomoże strona Pomoc i społeczność.",
    footnote: "Zrzuty ekranu pokazują serwer demonstracyjny z wymyślonymi graczami.",
  },

  features: {
    h1: "Postaw BeamMP dla znajomych, nie dotykając pliku konfiguracyjnego",
    lead: "EasyServer instaluje oficjalny serwer BeamMP, a potem daje ci jedną stronę do zarządzania nim. Za darmo, open source, działa na Windows i Linux.",
    howInstall: "Jak zainstalować",
    onPage: "Na tej stronie",
    online: "Wystawienie do sieci", onlineSub: "Tu utyka większość ludzi.",
    onlineRows: [
      ["Prowadzona instalacja", ["Wklej AuthKey, a instalator sprawdzi, czy jest ważny. Ustawia serwer tak, by startował z komputerem, i uruchamia go ponownie po awarii."]],
      ["Otwieranie portu", ["Jedno kliknięcie prosi router o otwarcie portu 30814. Jeśli twój router na to nie pozwala, strona Pomoc wyjaśnia, jak zrobić to ręcznie."]],
      ["„Czemu mój znajomy nie może dołączyć?”", ["Strona Stan sprawdza AuthKey, port, zaporę i to, czy serwer jest na liście BeamMP, i mówi, co jest nie tak."]],
      ["Stare laptopy mile widziane", ["Preset „Słaby komputer” pozwala na mniej graczy i aut i szybko sprząta porzucone auta, więc stary laptop uciągnie mały serwer."]],
    ],
    running: "Na co dzień", runningSub: "Przy biurku albo z kanapy.",
    playersAlt: "Strona graczy z listą graczy online i przyciskami wyrzucenia, wyciszenia i bana",
    playersCap: "Strona graczy",
    phoneAlt: "Panel na telefonie",
    phoneCap: "To samo na telefonie",
    runningRows: [
      ["Start, stop, zmiana mapy", ["Zmieniaj mapę z listy zamiast edytować ServerConfig.toml. Działa w każdej przeglądarce, także na telefonie."]],
      ["Gracze i bany", ["Wyrzucaj, wyciszaj i banuj z panelu, z Discorda albo komendą na czacie. Jest też lista zaproszonych i tryb konserwacji."]],
      ["Mody", ["Przeciągnij zip na stronę albo wybierz mod z repozytorium BeamNG. Każdy jest skanowany antywirusem, zanim gracze go pobiorą.", "Udostępnij całą listę modów krótkim kodem, a serwer znajomego zainstaluje ten sam zestaw."]],
      ["Kopie zapasowe i powiadomienia", ["Twórz kopię konfiguracji i przywracaj ją. Dostań wiadomość na Discordzie, e-mailem, na Telegramie albo na telefon, gdy serwer padnie."]],
    ],
    closing: "Pobierz, uruchom i idź za krokami. Większość osób jest online po około pięciu minutach. Jeśli utkniesz, pomoże strona Pomoc i społeczność.",
    footnote: "Wersja na Maca jest eksperymentalna i dostępna tylko w Rolling.",
  },

  help: {
    h1: "Pomoc i społeczność",
    lead: "Pytania, które właściciele serwerów zadają najczęściej, z odpowiedziami. Nie ma twojego? Zapytaj na forum społeczności.",
    search: "Szukaj, np. „znajomi nie mogą dołączyć” albo „mody”",
    searchLabel: "Szukaj pytań",
    topicsLabel: "Tematy",
    all: "Wszystkie",
    question: "pytanie", questions: { few: "pytania", many: "pytań", other: "pytania" }, match: "pasuje",
    results: "Wyniki", marked: "Pasujące słowa są zaznaczone.",
    mostAsked: "Najczęściej zadawane",
    copyLink: "Kopiuj link do tej odpowiedzi", linkCopied: "Link skopiowany",
    empty: "Nie ma jeszcze odpowiedzi na to. [Zapytaj na forum]({ASK}), a może trafi tutaj.",
    askTitle: "Nie znalazłeś odpowiedzi?",
    askText: "Zapytaj społeczność. Przeszukaj stare wątki, podziel się pomysłami albo pochwal się serwerem. Wystarczy darmowe konto na GitHubie.",
    askButton: "Zadaj pytanie",
    forumButton: "Otwórz forum",
    cats: {
      start: "Pierwsze kroki", join: "Dołączanie i sieć", mods: "Mody i mapy",
      dash: "Panel i logowanie", discord: "Discord i powiadomienia", trouble: "Problemy",
    },
    qa: [
      ["what-do-i-need", "start", "Czego potrzebuję, żeby postawić serwer?", [
        { ul: ["Komputera, który jest włączony, gdy gracie: dowolnego 64-bitowego PC z Windows 10/11 albo Linuksa (Ubuntu, Linux Mint, Debian, także Raspberry Pi 4/5 z 64-bitowym systemem). Dla grupy znajomych wystarczy stary laptop.",
          "Darmowego **AuthKey** BeamMP (zobacz następne pytanie).",
          "Własnej kopii BeamNG.drive do grania. Sam serwer jest darmowy."] },
        "Prędkość wysyłania ma większe znaczenie niż procesor: każdy gracz pobiera mody od ciebie."]],
      ["authkey", "start", "Skąd wziąć AuthKey?", [
        { ol: ["Wejdź na [keymaster.beammp.com](https://keymaster.beammp.com) i zaloguj się przez Discord.",
          "Kliknij **Keys**, potem **+**, i nadaj mu dowolną nazwę.",
          "Skopiuj klucz i wklej go do instalatora albo później w **Konfiguracja → AuthKey**."] },
        "Bez klucza serwer dalej działa w sieci domowej, tylko nie ma go na publicznej liście. Jeden klucz na jeden publiczny serwer."]],
      ["windows-or-linux", "start", "Windows czy Linux?", [
        "**Grasz na tym samym PC, na którym stoi serwer?** Windows jest najprostszy: pobierz zip i kliknij dwukrotnie **Install-BeamMP-Server.bat**.",
        "**Osobny komputer tylko na serwer?** Linux jest lepszy. Serwer działa w tle, sam startuje przy włączeniu komputera, wraca po awarii, a w **trybie laptopa** działa przy zamkniętej klapie. Jedna komenda instaluje wszystko."]],
      ["update", "start", "Jak zaktualizować EasyServer i serwer BeamMP?", [
        { ul: ["**Sam EasyServer:** strona **Aktualizacje** w panelu. Na Windows możesz też uruchomić najnowszy instalator na starej wersji; ustawienia zostaną.",
          "**Serwer BeamMP:** **Konfiguracja → Restarty i aktualizacje → instaluj aktualizacje BeamMP** aktualizuje go automatycznie przy zaplanowanym restarcie. Ręcznie: `beammp update` na Linuksie, **Update-BeamMP-Server.bat** na Windows."] }]],

      ["not-in-server-list", "join", "Mojego serwera nie ma na liście serwerów BeamMP", [
        { ol: ["**Konfiguracja → AuthKey** musi być wypełnione.",
          "**Konfiguracja → Prywatny** musi być wyłączone. Presety „Najbezpieczniej” i „Tylko znajomi” celowo ukrywają serwer.",
          "Port musi być osiągalny z internetu (zobacz następne pytanie).",
          "Daj mu minutę czy dwie po starcie."] },
        "**Stan → Sprawdź ponownie** sprawdza to wszystko i mówi, co jest nie tak."]],
      ["friends-cant-join", "join", "Znajomi w moim Wi-Fi mogą dołączyć, ale ci spoza domu nie", [
        "Twój router musi ich wpuścić. To ustawia się raz:",
        { ol: ["W routerze nadaj komputerowi z serwerem stały adres (często nazywa się to *rezerwacją DHCP* lub *statycznym IP*).",
          "**Przekieruj port 30814, TCP i UDP**, na ten komputer. Wyszukaj „*model twojego routera* przekierowanie portów”, żeby znaleźć dokładne menu.",
          "W panelu: **Stan → Pełne sprawdzenie**. „Osiągalny z internetu” powinno być zielone."] },
        "Dalej czerwone? Niektórzy dostawcy dzielą jeden adres między wiele domów (CGNAT) i wtedy przekierowanie portów nie może działać. Strona Stan powie ci, jeśli tak jest: poproś dostawcę o publiczny adres IPv4 albo użyj przekaźnika (**Ustawienia → Ukryj swoje IP**)."], true],
      ["one-player-cant-join", "join", "Jeden konkretny gracz nie może dołączyć", [
        "**Stan → Ktoś nie może dołączyć?** → wpisz jego nazwę w BeamMP → **Sprawdź**. Odczytuje jego ostatnią próbę i mówi, czemu się nie udała: ban, brak na liście zaproszonych, konserwacja, zablokowani goście, kod antybota, za dużo graczy z jednego połączenia, pełny serwer itd., razem z rozwiązaniem.",
        "Odrzuceni gracze pojawiają się też w **Konfiguracja → Kto może dołączyć → Ostatnio odrzuceni** z przyciskiem **+ zezwól**."]],
      ["password", "join", "Jak ustawić hasło na serwerze / zrobić go tylko dla znajomych?", [
        "BeamMP nie ma hasła do dołączania, więc EasyServer używa zamiast niego **listy zaproszonych**:",
        { ol: ["**Konfiguracja → Kto może dołączyć**: włącz listę i wpisz nazwy znajomych z BeamMP, po jednej w linii.",
          "**Zapisz listę**. Działa od razu, bez restartu."] },
        "Wszyscy inni dostają komunikat „tylko z zaproszeniem”. Najszybciej przez preset **Najbezpieczniej** albo **Tylko znajomi** w **Konfiguracja → Presety bezpieczeństwa**. Z botem Discord: `/whitelist add nazwa`."]],
      ["ip-changes", "join", "Mój domowy adres IP ciągle się zmienia", [
        "Ustaw darmową stałą nazwę: **Ustawienia → Stały adres (DuckDNS)**. Znajomi łączą się wtedy z `twojanazwa.duckdns.org` i działa to dalej, gdy adres się zmieni. Serwery publiczne tego nie potrzebują: lista serwerów zawsze ma aktualny adres."]],
      ["hide-ip", "join", "Czy gracze widzą moje domowe IP? A co z DDoS?", [
        "Gracze łączą się z twoim serwerem, więc tak, mogą poznać adres, jak przy każdym serwerze gry stawianym w domu. Jeśli cię to martwi, **Ustawienia → Ukryj swoje IP** puszcza graczy przez przekaźnik, a ochrona przed zalewaniem jest częścią presetów **Najbezpieczniej** i **Publiczny, ale bezpieczny**. Zobacz [Chroń swoje IP]({GH}/blob/main/PROTECT-YOUR-IP.md) (po angielsku)."]],

      ["add-mods", "mods", "Jak dodać mody?", [
        { ol: ["Otwórz **Mody** w panelu i przeciągnij pliki **.zip** z modami na stronę.",
          "Każdy najpierw sprawdza antywirus. Serwer restartuje się około 15 sekund później (na Windows kliknij Restart). To rozłącza graczy, więc dodawaj mody, gdy jest spokojnie.",
          "Mody z mapami dostają plakietkę **map:**. Kliknij **Użyj mapy**, żeby na niej grać."] },
        "Gracze niczego nie instalują: BeamMP pobiera dla nich mody przy dołączaniu. Można też użyć ikony na pulpicie **Drop BeamMP Mods Here** (Windows), folderu `BeamMP-Mods` albo `beammp addmod plik.zip` (Linux)."]],
      ["slow-joining", "mods", "Dołączanie trwa wieki przez pobieranie modów", [
        { ul: ["Włącz **tryb lekki** na stronie Mody: gracze pobierają tylko mapę, na której się gra. Pozostałe mody z mapami wracają same, gdy przełączysz na ich mapę.",
          "Usuń mody, których nikt nie używa. Karta na górze strony Mody pokazuje łączny rozmiar pobierania.",
          "Znajomi z wolnym internetem mogą dostać **paczkę modów** (Mody → Paczka modów) i przed dołączeniem skopiować pliki do `Documents\\BeamNG.drive\\mods\\multiplayer`."] },
        "Ograniczeniem jest tu twoja prędkość wysyłania, więc duża paczka będzie wolna na każdym domowym łączu."]],
      ["mod-blocked", "mods", "Antywirus zablokował mod. Czy naprawdę jest niebezpieczny?", [
        "EasyServer blokuje mody, które zawierają programy, zamaskowane pliki lub bomby zip, albo które oznaczy Microsoft Defender, ClamAV lub VirusTotal. Zwykły mod do BeamNG to tylko pliki aut, map i skryptów, więc zablokowany mod zawiera coś, czego mod mieć nie powinien. Powód jest pokazany obok.",
        "Zablokowane pliki nigdy nie trafiają na serwer ani do graczy. Pobierz mod ponownie z oficjalnego repozytorium BeamNG zamiast ze strony z reuploadami."]],
      ["change-map", "mods", "Jak zmienić mapę albo pozwolić graczom głosować?", [
        { ul: ["**Teraz:** **Przegląd → Mapa**, wybierz, potwierdź. Serwer restartuje się na nowej mapie.",
          "**Głosowanie:** **Konfiguracja → Głosowanie na mapę**, zaznacz dozwolone mapy. Gracze wpisują `/vote` na czacie w grze.",
          "**Automatycznie:** **Konfiguracja → Rotacja map** (co 1-24 godziny) albo **Konfiguracja → Wydarzenia** („Piątkowy wieczór driftu”)."] }]],

      ["forgot-password", "dash", "Zapomniałem hasła do panelu / zgubiłem telefon do logowania dwuetapowego", [
        { ul: ["**Windows:** kliknij dwukrotnie **Reset-Dashboard-Login.bat** w folderze EasyServer.",
          "**Linux:** `sudo beammp reset-login`"] },
        "Potem otwórz panel **na komputerze z serwerem** i wybierz nowe hasło. Logowanie dwuetapowe zostaje wyłączone, więc ustaw je ponownie na nowym telefonie."]],
      ["connection-reset", "dash", "Przeglądarka pisze „połączenie zresetowane” albo „niezabezpieczona”", [
        "**„Połączenie zresetowane”:** HTTPS jest włączony, ale otworzyłeś adres `http://`. Użyj `https://` albo zaktualizuj do 1.12.1 lub nowszej, która przekierowuje sama.",
        "**„Niezabezpieczona” / ostrzeżenie o certyfikacie:** za pierwszym razem to normalne. Panel tworzy własny certyfikat, więc przeglądarka go jeszcze nie zna. Porównaj odcisk pokazany w **Ustawieniach** z tym w ostrzeżeniu przeglądarki i kontynuuj. Aplikacja na Androida zapamięta go za ciebie."]],
      ["phone", "dash", "Czy mogę zarządzać serwerem z telefonu albo spoza domu?", [
        "**W domu:** otwórz `http://<ip-serwera>:30815` na telefonie albo zainstaluj aplikację na Androida (**BeamMP-EasyServer.apk** z [najnowszego wydania]({LATEST})) i zeskanuj kod QR w **Ustawienia → Aplikacja na telefon**. iPhone: Safari → Udostępnij → Do ekranu początkowego.",
        "**Z dowolnego miejsca:** włącz HTTPS i logowanie dwuetapowe, użyj hasła z 12+ znaków, potem **Ustawienia → Dostęp z internetu** i przekieruj port **30815 (TCP)**."]],
      ["stay-logged-in", "dash", "Czy może zapamiętać hasło, żebym nie logował się za każdym razem?", [
        "Tak (od wersji 1.12.1). Włącz **Nie wylogowuj mnie na tym urządzeniu** na stronie logowania. To urządzenie loguje się wtedy samo przez 30 dni od ostatniej wizyty, także po restartach. Menedżer haseł w przeglądarce też zaproponuje zapisanie hasła.",
        "Zgubiony telefon? **Ustawienia → Zapamiętane urządzenia → Zapomnij**."]],
      ["team", "dash", "Jak dać znajomym dostęp, żeby pomagali moderować?", [
        "**Ustawienia → Użytkownicy i role**: nazwa, rola, hasło → **Dodaj**.",
        { ul: ["**Widz**: patrzy, niczego nie zmienia", "**Moderator**: wyrzuca, wycisza, banuje, lista zaproszonych, restart, konserwacja", "**Admin**: wszystko oprócz użytkowników, haseł i dostępu z internetu"] },
        "Tylko do moderacji w grze dodaj ich nazwy z BeamMP w **Konfiguracja → Moderacja i antybot → Admini**. Wtedy mogą używać `/kick`, `/ban` i `/mute` na czacie w grze."]],

      ["discord-bot", "discord", "Jak skonfigurować bota Discord?", [
        { ol: ["[discord.com/developers/applications](https://discord.com/developers/applications) → **New Application**.",
          "**Installation** → Install Link: **None** → zapisz.",
          "**Bot** → wyłącz **Public Bot** i włącz **Message Content Intent** (do mostu czatu) → **Reset Token** → kopiuj.",
          "Panel: **Ustawienia → Bot Discord** → wklej token, włącz, **Zapisz**. Gdy pojawi się **Online**, kliknij **Dodaj bota do swojego Discorda**.",
          "Wpisz `/status` na Discordzie."] },
        "Nigdy nikomu nie udostępniaj tokenu bota. Jeśli wycieknie, kliknij ponownie Reset Token."]],
      ["slash-commands", "discord", "Bot jest online, ale komendy z ukośnikiem się nie pokazują", [
        { ul: ["Nowe komendy mogą potrzebować minuty. Uruchom ponownie Discorda (Ctrl+R na PC).",
          "Sprawdź, czy w **Ustawienia → Bot Discord** jako serwer Discorda, na którym odpowiada bot, wybrany jest twój.",
          "`/start`, `/stop`, `/restart` i `/whitelist` widzą tylko osoby z uprawnieniem **Zarządzanie serwerem** albo użytkownicy Discorda, którym na to pozwoliłeś."] }]],
      ["alerts", "discord", "Czy mogę dostać powiadomienie, gdy serwer padnie albo ktoś dołączy?", [
        "Tak, na telefon (darmowa aplikacja **ntfy**, **Ustawienia → Aplikacja na telefon**), na Discorda, Telegrama, Slacka i inne aplikacje albo e-mailem. O czym chcesz wiedzieć, wybierasz w **Powiadamiaj mnie o**. **Konfiguracja → Powiadomienia o dołączeniu** daje znać, gdy dołączą wybrani gracze."]],

      ["crash-lag", "trouble", "Serwer ciągle pada albo laguje", [
        { ol: ["**Logi → Wyjaśnij cały log** wypisuje każdy błąd prostym językiem, w tym zepsute mody i brak pamięci.",
          "**Stan** pokazuje pamięć i dysk, a **Ustawienia → Obciążenie komputera** ma wykresy z 24 godzin.",
          "Na starszym komputerze użyj presetu **Słaby komputer**, zmniejsz maksymalną liczbę aut i włącz tryb lekki."] },
        "Serwer po awarii uruchamia się sam, a ty dostajesz wiadomość, jeśli powiadomienia o awariach są włączone."]],
      ["undo", "trouble", "Zmieniłem ustawienie i teraz coś nie działa", [
        "**Konfiguracja → Co się zmieniło?** przechowuje 40 ostatnich wersji konfiguracji, razem z tym, kto co zmienił. **Porównaj z obecną** pokazuje różnicę, a **Przywróć** cofa zmiany. AuthKey zostaje, a cofnięcie też możesz cofnąć."]],
      ["sleep", "trouble", "Czy komputer musi chodzić 24/7?", [
        "Nie. **Ustawienia → Usypianie i budzenie** usypia go, gdy przez jakiś czas nikt nie grał, i budzi przed wydarzeniami. Z **Wake-on-LAN** (potrzebny kabel sieciowy) znajomi mogą go obudzić komendą `/start` na Discordzie albo przyciskiem **Obudź** w aplikacji. Wynik zgodności pokazuje, co jeszcze trzeba ustawić."]],
      ["new-computer", "trouble", "Jak przenieść serwer na nowy komputer?", [
        { ol: ["Stary komputer: **Ustawienia → Kopia / przeniesienie na inny komputer → Eksportuj ustawienia + mody**.",
          "Zainstaluj EasyServer na nowym, a potem **Importuj…** ten plik.",
          "Wklej ponownie AuthKey: klucze i hasła nigdy nie trafiają do eksportu."] },
        "Nocne kopie zapasowe są domyślnie włączone, a 7 ostatnich możesz pobrać w każdej chwili."]],
      ["get-help", "trouble", "Mojego problemu tu nie ma. Jak dostać pomoc?", [
        { ol: ["**Stan → Pobierz raport diagnostyczny**. Klucze, hasła i adresy są z niego usuwane.",
          "[Zapytaj na forum społeczności]({ASK}) i dołącz raport. Błędy zgłaszaj w [issues]({GH}/issues/new/choose)."] },
        "Znalazłeś problem z bezpieczeństwem? Użyj [prywatnego zgłoszenia]({GH}/security/advisories/new) zamiast publikować go publicznie."]],
    ],
  },
  // Translations of the "What's new" cards, by version. The cards themselves come from the
  // <!-- website --> block in CHANGELOG.md; when a new version has no translation here yet, it shows in English.
  whatsNew: {
    "1.15": [
      ["Zasady pojazdów", "Blokuj rekwizyty, przyczepy lub dowolne auta i zatrzymaj spam spawnów. Modowe auta tak ciężkie, że wszystkim zacina, są wykrywane automatycznie."],
      ["Pluginy serwera", "Instaluj tryby gry od społeczności, jak CareerMP, freeRoamMP i BeamJoy, prosto ze strony każdego autora."],
      ["Prowadźcie go zespołem", "Zaproś znajomych linkiem, który działa raz i wygasa po godzinie, i wybierz, co każdy może robić na każdym serwerze. Mogą logować się przez Discorda."],
    ],
  },
  notFound: {
    title: "Nie znaleziono strony - BeamMP EasyServer",
    h1: "404: zły zakręt",
    joke: "Ta strona rozbiła się mocniej niż auto w BeamNG przy pełnej prędkości i nie ma dla niej przycisku resetu.",
    text: "Skoro już tu jesteś, sprawdź, jak daleko dojedziesz.",
    start: "Naciśnij spację albo dotknij drogi, żeby ruszyć",
    again: "Rozbity! Naciśnij spację albo dotknij, żeby spróbować jeszcze raz",
    best: "Rekord",
    gameLabel: "Minigra: samochód przeskakuje pachołki i opony",
    home: "Wróć na stronę główną",
    help: "Pomoc i FAQ",
  },
};
