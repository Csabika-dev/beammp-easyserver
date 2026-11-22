// Website text in Spanish. Same structure as en.js; anything left out shows in English.
export default {
  meta: {
    home: {
      title: "BeamMP EasyServer - tu propio servidor multijugador de BeamNG.drive en un clic",
      description: "Instalador de un clic y panel web gratis para servidores BeamMP (multijugador de BeamNG.drive) en Windows y Linux. Mods con análisis antivirus, estadísticas de jugadores, moderación, Discord y app para el móvil.",
      ogTitle: "BeamMP EasyServer",
      ogDescription: "Monta tu propio servidor multijugador de BeamNG.drive en un clic y contrólalo desde el móvil.",
    },
    features: {
      title: "Funciones - BeamMP EasyServer",
      description: "Lo que hace BeamMP EasyServer: instalación guiada, un panel que puedes usar desde el móvil, mods analizados contra virus, reglas de vehículos, plugins de servidor y cuentas de equipo. Gratis para Windows y Linux.",
      ogTitle: "BeamMP EasyServer - funciones",
      ogDescription: "Monta un servidor BeamMP para tus amigos sin editar archivos de configuración.",
    },
    help: {
      title: "Ayuda y comunidad - BeamMP EasyServer",
      description: "Respuestas a las preguntas más comunes sobre BeamMP EasyServer: los amigos no pueden entrar, abrir puertos, mods, entrada lenta, contraseña olvidada, bot de Discord, cierres. Pregunta a la comunidad si la tuya no está.",
      ogTitle: "BeamMP EasyServer - Ayuda y comunidad",
      ogDescription: "Preguntas frecuentes con respuestas, y un foro de la comunidad para todo lo demás.",
    },
  },

  nav: {
    start: "Empezar", what: "Qué hace", downloads: "Descargas", faq: "Preguntas",
    features: "Funciones", help: "Ayuda", language: "Idioma",
  },

  common: {
    download: "Descargar",
    copy: "Copiar", copied: "Copiado", pressCtrlC: "Pulsa Ctrl+C",
    license: "Licencia MIT. No está hecho por el equipo de BeamMP ni por BeamNG GmbH, ni tiene relación con ellos. EasyServer se basa en su trabajo y en el de muchos autores de mods y plugins: [ver los créditos]({GH}#-credits).",
    tryTitle: "Pruébalo en tu PC",
    viewOnGithub: "Ver en GitHub",
  },

  tour: {
    label: "Páginas del panel",
    tabs: ["Resumen", "Mods", "Jugadores", "Página de estado"],
    alts: [
      "El panel de EasyServer: servidor en marcha, 7 de 16 jugadores conectados, mapa, tiempo activo y quién está conectado",
      "Página de mods con los resultados del antivirus y el modo ligero ahorrando 380 MB",
      "Estadísticas de jugadores: jugadores por día, horas con más gente y resumen semanal",
      "Página de estado pública con la disponibilidad de 30 días",
    ],
  },

  home: {
    h1: "Tu propio servidor multijugador de BeamNG.drive, listo en un clic",
    lead: "EasyServer instala el servidor oficial de BeamMP y te da un panel para manejarlo desde el PC o el móvil. Añade mods, mira quién juega y deja fuera a los trolls, sin archivos de configuración ni línea de comandos. Es gratis y de código abierto, para Windows y Linux.",
    how: "Cómo funciona",

    startTitle: "Empezar",
    startSub: "Unos diez minutos, casi todo esperando a las descargas.",
    stepsLabel: "Pasos de instalación",
    back: "Atrás",
    next: "Siguiente:",
    steps: [
      { short: "AuthKey", title: "Consigue una AuthKey gratis",
        text: ["Entra en [keymaster.beammp.com](https://keymaster.beammp.com) con Discord, haz clic en **Keys**, luego en **+**, y copia la clave. Así tu servidor aparece en la lista pública de BeamMP."] },
      { short: "Instalar", title: "Instalar",
        text: ["Esto instala la versión **Stable**, ya probada. Para las funciones más nuevas, mira [Rolling](#versions)."] },
      { short: "Panel", title: "Abre el panel",
        text: ["En el ordenador del servidor, ve a **http://localhost:30815** y elige una contraseña. Desde el móvil u otro PC de casa, usa **http://<ip-del-servidor>:30815**."] },
      { short: "Amigos", title: "Deja entrar a tus amigos",
        text: ["En la página **Estado**, haz clic en **Abrir el puerto automáticamente**. La mayoría de routers lo aceptan. Si el tuyo no, abre tú el puerto 30814 (TCP y UDP), y la página Estado te dice cuándo funciona.",
          "Luego haz clic en **Copiar invitación** y pégala en Discord. [Guías paso a paso]({GH}#-guides) (en inglés)"] },
    ],
    osLabel: "Tu sistema",
    windows: "Windows", linux: "Linux",
    winInstall: "Descarga **BeamMP-EasyServer-Windows.zip** de la [última versión]({LATEST}), descomprímelo y haz doble clic en **Install-BeamMP-Server.bat**.",
    linuxInstall: "Pega esto en una terminal:",
    videoTitle: "Cómo crear un servidor BeamMP en 5 minutos - vídeo de instalación (en inglés)",
    videoNote: "¿Prefieres verlo? Toda la instalación dura unos 2 minutos. [Abrir en YouTube](https://youtu.be/DWD9HcW1OIc)",

    whatTitle: "Qué hace",
    whatSub: "Pensado para quien quiere jugar con amigos, no aprender a administrar servidores. [Todas las funciones](features.html)",
    featuresLabel: "Funciones",
    features: [
      { title: "Mods sin preocupaciones",
        alt: "Página de mods con los resultados del antivirus y el modo ligero ahorrando 380 MB",
        text: "Arrastra los zip de los mods a la página. Cada uno se revisa en busca de programas ocultos, archivos disfrazados y bombas zip con Microsoft Defender o ClamAV, y VirusTotal si quieres, antes de que los jugadores puedan descargarlo.",
        list: ["**Buscador de mods:** instala desde el repositorio de BeamNG en un clic, y actualiza igual",
          "**Modo ligero:** los jugadores solo descargan el mapa que se está jugando, así entran antes",
          "**Paquetes de mods:** mueve o comparte todos tus mods en un solo archivo"] },
      { title: "Mira quién juega, y cuándo",
        alt: "Estadísticas de jugadores: jugadores por día, horas con más gente y resumen semanal",
        text: "Jugadores por día, las horas con más gente, un mapa de calor semanal, los mejores jugadores, los récords del servidor y los mapas en los que la gente de verdad se queda.",
        list: ["**Expulsa, silencia y banea** desde el panel, Discord o el chat del juego",
          "**Modo mantenimiento** cierra el servidor mientras trabajas en él",
          "**Cuentas de equipo** para los amigos que ayudan, solo con los permisos que tú les des"] },
      { title: "Elige lo abierto que está",
        alt: "Preajustes de seguridad: Lo más seguro, Público pero seguro, Solo amigos, Abierto a todos, Ordenador lento",
        text: "Un clic pone tu servidor en cualquier punto entre **Lo más seguro** (solo con invitación, anti-bots, protección contra inundaciones) y **Abierto a todos**. Cada cambio de configuración se guarda, así ves qué cambió y puedes deshacerlo.",
        list: ["**Lista de invitados,** porque BeamMP no tiene contraseña para entrar",
          "**Anti-bots:** códigos de entrada, bloqueo de invitados y límites de conexiones"] },
      { title: "Contrólalo desde el móvil",
        alt: "El panel en un móvil",
        text: "El panel funciona en cualquier navegador del móvil. Hay app para Android, y en iPhone puedes añadirlo a la pantalla de inicio.",
        list: ["**Avisos** de cierres, entradas y actualizaciones en el móvil, Discord, Telegram, Slack o por correo",
          "**Bot de Discord** con /status, /start, /restart, /whitelist y un puente de chat",
          "**Suspensión y Wake-on-LAN,** para que el PC no tenga que estar encendido todo el día"] },
      { title: "Una página de estado para los jugadores",
        alt: "Página de estado pública con la disponibilidad de 30 días",
        text: "Un enlace muestra si el servidor está en marcha, quién está conectado, qué mods descargar y el próximo evento. Sin iniciar sesión, y sin mostrar direcciones ni ajustes." },
    ],

    newTitle: "Novedades de 1.15",
    newSub: "Ya en Rolling. Pasan a Stable cuando están probadas.",
    news: [
      ["Reglas de vehículos", "Bloquea objetos, remolques o cualquier coche, y frena el spam de apariciones. Los coches mod tan pesados que dan tirones a todos se detectan solos."],
      ["Plugins de servidor", "Instala modos de juego de la comunidad como CareerMP, freeRoamMP y BeamJoy, directamente desde la página de cada autor."],
      ["Gestionadlo en equipo", "Invita a amigos con un enlace que funciona una vez y caduca a la hora, y elige qué puede hacer cada uno en cada servidor. Pueden entrar con Discord."],
    ],

    alsoTitle: "También incluye",
    alsoSub: "Todo opcional. Activa lo que necesites.",
    also: [
      ["Copiar invitación", "Un mensaje listo para Discord con la dirección y el puerto."],
      ["Votación y rotación de mapas", "Los jugadores escriben /vote, o el mapa cambia según un horario."],
      ["Eventos semanales", "«Noche de drift del viernes» cambia el mapa y los mods y se anuncia en Discord."],
      ["/tp y /repair", "Teletranspórtate con tus amigos cuando acepten, con reglas de reparación realistas o hardcore."],
      ["Limpieza de coches", "Los coches abandonados se quitan, con cuenta atrás antes de la limpieza nocturna."],
      ["Herramientas de chat", "Mensaje de bienvenida, anuncios programados, filtro de chat, anti-spam y /countdown."],
      ["Varios servidores", "Más de un servidor en un PC, cada uno con sus propios límites de CPU, RAM y descargas."],
      ["Copias nocturnas", "Restaura, o muévete a otro ordenador, con un solo archivo."],
      ["Oculta tu IP", "Un relé opcional y protección contra inundaciones frente a DDoS."],
      ["Explicador de registros", "Los errores del servidor en lenguaje claro, con lo que hay que hacer."],
    ],

    secTitle: "Seguridad",
    secSub: "Tu servidor es un ordenador de tu red de casa, así que esto importa.",
    security: [
      ["Las claves van cifradas", "Tu AuthKey, tokens y contraseñas nunca se guardan en texto plano."],
      ["Usuarios separados en Linux", "El servidor del juego y el panel funcionan cada uno con su propio usuario limitado."],
      ["Inicio de sesión en dos pasos", "Obligatorio antes de que el panel sea accesible desde internet."],
      ["Probado en cada cambio", "Pruebas automáticas intentan colarse en cada página del panel y en el plugin del juego con cada actualización."],
    ],

    dlTitle: "Descargas",
    dlSub: "Las dos son gratis. ¿No lo tienes claro? Elige Stable.",
    stable: "Stable",
    stableWhat: "Probada. Es la versión marcada como «Latest» en GitHub.",
    stableWin: "**Windows:** descarga **BeamMP-EasyServer-Windows.zip**, descomprímelo y haz doble clic en **Install-BeamMP-Server.bat**",
    linuxLabel: "**Linux:**",
    stableButton: "Descargar Stable",
    rolling: "Rolling",
    rollingWhat: "Funciones nuevas en cuanto están hechas. Puede tener errores.",
    rollingWin: "**Windows:** descarga el ZIP, descomprímelo, abre la carpeta **windows** y haz doble clic en **Install-BeamMP-Server.bat**",
    mac: "**Mac (experimental, solo Rolling):** pega esto en Terminal. Ejecuta el servidor en una pequeña máquina virtual Linux que arranca con tu Mac ([cómo funciona]({GH}#mac-experimental)).",
    broken: "¿Algo roto? Instala Stable encima. Tus ajustes y mods se conservan.",
    rollingButton: "Descargar Rolling (ZIP)",
    changes: "Qué cambió en cada versión: [registro de cambios]({GH}/blob/main/CHANGELOG.md), [todas las versiones]({GH}/releases)",

    faqTitle: "Preguntas",
    faqSub: "[Más respuestas y la comunidad](help.html)",
    faq: [
      ["¿Es gratis?", "Sí. Es gratis y de código abierto (licencia MIT), con todas las funciones y sin anuncios. BeamMP y su servidor también son gratis. Para jugar necesitas tu propia copia de BeamNG.drive."],
      ["¿Es el servidor oficial de BeamMP?", "EasyServer instala el servidor **oficial** de BeamMP y lo mantiene actualizado. EasyServer es un proyecto de la comunidad, no lo hace ni lo respalda el equipo de BeamMP."],
      ["¿Qué ordenador necesito?", "Cualquier PC de 64 bits con Windows 10 u 11, o Linux (Ubuntu, Linux Mint, Debian y otros, incluida una Raspberry Pi 4 o 5 con sistema de 64 bits). Un portátil viejo basta para un grupo de amigos. La velocidad de subida importa más que el procesador."],
      ["¿Cambia algo en mi router?", "Solo si haces clic en **Abrir el puerto automáticamente**, que pide al router que abra el puerto del juego. Si no, solo abre el puerto en el cortafuegos del propio ordenador, y pregunta antes."],
      ["¿Puedo usarlo desde el móvil?", "Sí. El panel funciona en cualquier navegador del móvil, hay app para Android y puedes añadirlo a la pantalla de inicio del iPhone. Manejarlo desde fuera de casa funciona cuando activas HTTPS y el inicio de sesión en dos pasos."],
      ["He encontrado un error o tengo una idea", "[Abre una incidencia en GitHub]({GH}/issues/new/choose). Para problemas de seguridad, usa mejor el aviso privado."],
    ],

    closing: "Descárgalo, ejecútalo y sigue los pasos. Si te atascas, la página de ayuda y la comunidad te echan una mano.",
    footnote: "Las capturas muestran un servidor de demostración con jugadores inventados.",
  },

  features: {
    h1: "Monta BeamMP para tus amigos sin tocar un archivo de configuración",
    lead: "EasyServer instala el servidor oficial de BeamMP y te da una sola página para manejarlo. Es gratis, de código abierto y funciona en Windows y Linux.",
    howInstall: "Cómo instalarlo",
    onPage: "En esta página",
    online: "Ponerlo en línea", onlineSub: "La parte en la que se atasca casi todo el mundo.",
    onlineRows: [
      ["Instalación guiada", ["Pega tu AuthKey y el instalador comprueba que es válida. Hace que el servidor arranque con tu PC y lo reinicia si se cierra."]],
      ["Abrir el puerto", ["Un clic pide a tu router que abra el puerto 30814. Si tu router no lo permite, la página de ayuda explica cómo hacerlo a mano."]],
      ["«¿Por qué no puede entrar mi amigo?»", ["La página Estado comprueba tu AuthKey, el puerto, el cortafuegos y si tu servidor aparece en la lista de BeamMP, y te dice cuál falla."]],
      ["Portátiles viejos bienvenidos", ["El preajuste «Ordenador lento» permite menos jugadores y coches y quita rápido los coches abandonados, así un portátil sobrante puede llevar un servidor pequeño."]],
    ],
    running: "En marcha", runningSub: "Desde el escritorio o desde el sofá.",
    playersAlt: "Página de jugadores con la lista de conectados y botones para expulsar, silenciar y banear",
    playersCap: "La página de jugadores",
    phoneAlt: "El panel en un móvil",
    phoneCap: "Lo mismo en el móvil",
    runningRows: [
      ["Arrancar, parar, cambiar de mapa", ["Cambia el mapa desde una lista en vez de editar ServerConfig.toml. Funciona en cualquier navegador, también en el móvil."]],
      ["Jugadores y baneos", ["Expulsa, silencia y banea desde el panel, desde Discord o con un comando de chat. También hay una lista de invitados y modo mantenimiento."]],
      ["Mods", ["Arrastra un zip a la página o elige uno del repositorio de BeamNG. Cada uno se analiza contra virus antes de que lo descarguen los jugadores.", "Comparte tu lista entera de mods con un código corto, y el servidor de un amigo puede instalar los mismos."]],
      ["Copias y avisos", ["Haz copia de tu configuración y restáurala. Recibe un mensaje en Discord, por correo, Telegram o en el móvil cuando el servidor se cierra."]],
    ],
    newTitle: "Novedades de 1.15", newSub: "Ya en la versión Rolling. Pasan a Stable cuando están probadas.",
    newRows: [
      ["Reglas de vehículos", ["Bloquea objetos, los enormes objetos con física, remolques o cualquier coche que elijas. Los coches mod tan pesados que dan tirones a todos se detectan solos.", "También hay un tiempo de espera entre apariciones, y preajustes para servidores de carreras y de rol."]],
      ["Plugins de servidor", ["Instala modos de juego de la comunidad como CareerMP, freeRoamMP y BeamJoy. Se descargan de la página de cada autor, y antes de instalar ves qué archivos van a dónde."]],
      ["Gestionadlo en equipo", ["Manda a un amigo un enlace de invitación que funciona una vez y deja de funcionar a la hora. Dale un rol, como espectador o moderador, en cada servidor.", "Pueden entrar con Discord en vez de contraseña. Quien entre desde fuera de tu red de casa necesita un código de inicio de sesión en dos pasos."]],
    ],
    closing: "Descárgalo, ejecútalo y sigue los pasos. La mayoría está en línea en unos cinco minutos. Si te atascas, la página de ayuda y la comunidad te echan una mano.",
    footnote: "La versión para Mac es experimental y solo está en Rolling.",
  },

  help: {
    h1: "Ayuda y comunidad",
    lead: "Las preguntas que más hacen los dueños de servidores, con respuestas. ¿No está la tuya? Pregunta en el foro de la comunidad.",
    search: "Busca, p. ej. «amigos no pueden entrar» o «mods»",
    searchLabel: "Buscar preguntas",
    topicsLabel: "Temas",
    all: "Todas",
    question: "pregunta", questions: "preguntas", match: "coinciden",
    results: "Resultados", marked: "Las palabras que coinciden están marcadas.",
    mostAsked: "La más preguntada",
    copyLink: "Copiar enlace a esta respuesta", linkCopied: "Enlace copiado",
    empty: "Todavía no hay respuesta para eso. [Pregúntalo en el foro]({ASK}) y puede que acabe aquí.",
    askTitle: "¿No encuentras tu respuesta?",
    askText: "Pregunta a la comunidad. Busca hilos antiguos, comparte ideas o presume de servidor. Solo necesitas una cuenta gratis de GitHub.",
    askButton: "Hacer una pregunta",
    forumButton: "Abrir el foro",
    cats: {
      start: "Primeros pasos", join: "Entrar y red", mods: "Mods y mapas",
      dash: "Panel e inicio de sesión", discord: "Discord y avisos", trouble: "Problemas",
    },
    qa: [
      ["what-do-i-need", "start", "¿Qué necesito para montar un servidor?", [
        { ul: ["Un ordenador que esté encendido mientras jugáis: cualquier PC de 64 bits con Windows 10/11, o Linux (Ubuntu, Linux Mint, Debian, también una Raspberry Pi 4/5 con sistema de 64 bits). Un portátil viejo vale para un grupo de amigos.",
          "Una **AuthKey** de BeamMP gratis (mira la siguiente pregunta).",
          "Tu propia copia de BeamNG.drive para jugar. El servidor en sí es gratis."] },
        "La velocidad de subida importa más que el procesador: cada jugador descarga tus mods desde ti."]],
      ["authkey", "start", "¿Dónde consigo la AuthKey?", [
        { ol: ["Ve a [keymaster.beammp.com](https://keymaster.beammp.com) y entra con Discord.",
          "Haz clic en **Keys**, luego en **+**, y ponle cualquier nombre.",
          "Copia la clave y pégala en el instalador, o más tarde en **Configuración → AuthKey**."] },
        "Sin clave el servidor funciona igual en tu red de casa, solo que no sale en la lista pública. Una clave por servidor público."]],
      ["windows-or-linux", "start", "¿Uso Windows o Linux?", [
        "**¿Juegas en el mismo PC donde está el servidor?** Windows es lo más fácil: descarga el zip y haz doble clic en **Install-BeamMP-Server.bat**.",
        "**¿Un ordenador aparte solo para el servidor?** Linux es mejor. El servidor va en segundo plano, arranca solo al encender el ordenador, se reinicia tras un cierre y con el **modo portátil** sigue funcionando con la tapa cerrada. Un comando lo instala todo."]],
      ["update", "start", "¿Cómo actualizo EasyServer y el servidor de BeamMP?", [
        { ul: ["**EasyServer:** la página **Actualizaciones** del panel. En Windows también puedes ejecutar el instalador nuevo encima del viejo; tus ajustes se conservan.",
          "**El servidor de BeamMP:** **Configuración → Reinicios y actualizaciones → instalar actualizaciones de BeamMP** lo actualiza solo en el reinicio programado. A mano: `beammp update` en Linux, **Update-BeamMP-Server.bat** en Windows."] }]],

      ["not-in-server-list", "join", "Mi servidor no sale en la lista de servidores de BeamMP", [
        { ol: ["**Configuración → AuthKey** tiene que estar rellena.",
          "**Configuración → Privado** tiene que estar desactivado. Los preajustes «Lo más seguro» y «Solo amigos» ocultan el servidor a propósito.",
          "El puerto tiene que ser accesible desde internet (mira la siguiente pregunta).",
          "Dale uno o dos minutos después de arrancarlo."] },
        "**Estado → Comprobar de nuevo** revisa todo esto y te dice qué falla."]],
      ["friends-cant-join", "join", "Mis amigos en mi Wi-Fi pueden entrar, pero los de fuera de casa no", [
        "Tu router tiene que dejarles pasar. Se configura una sola vez:",
        { ol: ["En el router, dale al ordenador del servidor una dirección fija (suele llamarse *reserva DHCP* o *IP estática*).",
          "**Redirige el puerto 30814, TCP y UDP**, a ese ordenador. Busca «*modelo de tu router* abrir puertos» para encontrar el menú exacto.",
          "En el panel: **Estado → Comprobación completa**. «Accesible desde internet» debería salir en verde."] },
        "¿Sigue en rojo? Algunos proveedores comparten una dirección entre muchas casas (CGNAT), y entonces abrir puertos no puede funcionar. La página Estado te avisa cuando es así: pide a tu proveedor una IPv4 pública, o usa un relé (**Ajustes → Oculta tu IP**)."], true],
      ["one-player-cant-join", "join", "Un jugador concreto no puede entrar", [
        "**Estado → ¿Alguien no puede entrar?** → escribe su nombre de BeamMP → **Comprobar**. Lee su último intento y te dice por qué falló: baneado, no está en la lista de invitados, mantenimiento, invitados bloqueados, código anti-bots, demasiados jugadores desde una conexión, servidor lleno, etc., con la solución.",
        "Los jugadores rechazados también salen en **Configuración → Quién puede entrar → Rechazados recientemente** con un botón **+ permitir**."]],
      ["password", "join", "¿Cómo pongo contraseña al servidor / lo dejo solo para amigos?", [
        "BeamMP no tiene contraseña para entrar, así que EasyServer usa una **lista de invitados**:",
        { ol: ["**Configuración → Quién puede entrar**: activa la lista y escribe los nombres de BeamMP de tus amigos, uno por línea.",
          "**Guardar lista**. Funciona al momento, sin reiniciar."] },
        "Los demás reciben un mensaje de «solo con invitación». Lo más rápido es el preajuste **Lo más seguro** o **Solo amigos** en **Configuración → Preajustes de seguridad**. Con el bot de Discord: `/whitelist add nombre`."]],
      ["ip-changes", "join", "La IP de mi casa cambia todo el rato", [
        "Configura un nombre fijo gratis: **Ajustes → Dirección fija (DuckDNS)**. Tus amigos se conectan entonces a `tunombre.duckdns.org`, y sigue funcionando aunque cambie la dirección. Los servidores públicos no lo necesitan: la lista de servidores siempre tiene la dirección actual."]],
      ["hide-ip", "join", "¿Los jugadores pueden ver la IP de mi casa? ¿Y los DDoS?", [
        "Los jugadores se conectan a tu servidor, así que sí, pueden averiguar la dirección, como con cualquier servidor de juego casero. Si te preocupa, **Ajustes → Oculta tu IP** hace pasar a los jugadores por un relé, y la protección contra inundaciones va incluida en los preajustes **Lo más seguro** y **Público pero seguro**. Mira [Protege tu IP]({GH}/blob/main/PROTECT-YOUR-IP.md) (en inglés)."]],

      ["add-mods", "mods", "¿Cómo añado mods?", [
        { ol: ["Abre **Mods** en el panel y arrastra los archivos **.zip** de los mods a la página.",
          "Cada uno se analiza contra virus primero. El servidor se reinicia unos 15 segundos después (en Windows, pulsa Reiniciar). Eso desconecta a los jugadores, así que añade mods cuando haya poca gente.",
          "Los mods de mapa llevan la etiqueta **map:**. Haz clic en **Usar mapa** para jugarlo."] },
        "Los jugadores no instalan nada: BeamMP les descarga los mods al entrar. También puedes usar el icono del escritorio **Drop BeamMP Mods Here** (Windows), la carpeta `BeamMP-Mods` o `beammp addmod archivo.zip` (Linux)."]],
      ["slow-joining", "mods", "Entrar tarda una eternidad por la descarga de mods", [
        { ul: ["Activa el **modo ligero** en la página Mods: los jugadores solo descargan el mapa que se está jugando. Los demás mods de mapa vuelven solos cuando cambias a su mapa.",
          "Quita los mods que nadie usa. La tarjeta de arriba de la página Mods muestra la descarga total.",
          "Los amigos con internet lento pueden recibir un **paquete de mods** (Mods → Paquete de mods) y copiar los archivos en `Documents\\BeamNG.drive\\mods\\multiplayer` antes de entrar."] },
        "Aquí el límite es tu velocidad de subida, así que un paquete grande va lento con cualquier conexión de casa."]],
      ["mod-blocked", "mods", "El antivirus bloqueó un mod. ¿De verdad es peligroso?", [
        "EasyServer bloquea los mods que contienen programas, archivos disfrazados o bombas zip, o que Microsoft Defender, ClamAV o VirusTotal marcan. Un mod normal de BeamNG solo tiene archivos de coches, mapas y scripts, así que un mod bloqueado lleva algo que un mod no debería llevar. El motivo aparece al lado.",
        "Los archivos bloqueados nunca llegan al servidor ni a tus jugadores. Vuelve a descargar el mod del repositorio oficial de BeamNG en vez de una web de resubidas."]],
      ["change-map", "mods", "¿Cómo cambio el mapa o dejo que voten los jugadores?", [
        { ul: ["**Ahora:** **Resumen → Mapa**, elige uno y confirma. El servidor se reinicia en el mapa nuevo.",
          "**Votación:** **Configuración → Votación de mapa**, marca los mapas permitidos. Los jugadores escriben `/vote` en el chat del juego.",
          "**Automático:** **Configuración → Rotación de mapas** (cada 1-24 horas) o **Configuración → Eventos** («Noche de drift del viernes»)."] }]],

      ["forgot-password", "dash", "Olvidé la contraseña del panel / perdí el móvil del inicio en dos pasos", [
        { ul: ["**Windows:** haz doble clic en **Reset-Dashboard-Login.bat** en la carpeta de EasyServer.",
          "**Linux:** `sudo beammp reset-login`"] },
        "Luego abre el panel **en el ordenador del servidor** y elige una contraseña nueva. El inicio en dos pasos queda desactivado, así que vuelve a configurarlo con tu móvil nuevo."]],
      ["connection-reset", "dash", "El navegador dice «conexión restablecida» o «no seguro»", [
        "**«Conexión restablecida»:** HTTPS está activado pero abriste una dirección `http://`. Usa `https://`, o actualiza a la 1.12.1 o posterior, que te lleva allí sola.",
        "**«No seguro» / aviso de certificado:** normal la primera vez. Tu panel crea su propio certificado, así que el navegador aún no lo conoce. Compara la huella que sale en **Ajustes** con la del aviso del navegador y continúa. La app de Android la recuerda por ti."]],
      ["phone", "dash", "¿Puedo manejar el servidor desde el móvil o desde fuera de casa?", [
        "**En casa:** abre `http://<ip-del-servidor>:30815` en el móvil, o instala la app de Android (**BeamMP-EasyServer.apk** de la [última versión]({LATEST})) y escanea el código QR de **Ajustes → App para el móvil**. iPhone: Safari → Compartir → Añadir a pantalla de inicio.",
        "**Desde cualquier sitio:** activa HTTPS y el inicio en dos pasos, usa una contraseña de 12 caracteres o más, y luego **Ajustes → Acceso desde internet** y abre el puerto **30815 (TCP)**."]],
      ["stay-logged-in", "dash", "¿Puede recordar mi contraseña para no entrar cada vez?", [
        "Sí (versión 1.12.1 y posteriores). Activa **Mantener la sesión en este dispositivo** en la página de inicio de sesión. Ese dispositivo entra solo durante 30 días desde la última visita, también tras reinicios. El gestor de contraseñas del navegador también ofrece guardarla.",
        "¿Perdiste un móvil? **Ajustes → Dispositivos recordados → Olvidar**."]],
      ["team", "dash", "¿Cómo doy acceso a amigos para que ayuden a moderar?", [
        "**Ajustes → Usuarios y roles**: nombre, rol, contraseña → **Añadir**.",
        { ul: ["**Espectador**: mirar, sin cambiar nada", "**Moderador**: expulsar, silenciar, banear, lista de invitados, reiniciar, mantenimiento", "**Admin**: todo menos usuarios, contraseñas y acceso desde internet"] },
        "Solo para moderar dentro del juego, añade sus nombres de BeamMP en **Configuración → Moderación y anti-bots → Admins**. Entonces pueden usar `/kick`, `/ban` y `/mute` en el chat del juego."]],

      ["discord-bot", "discord", "¿Cómo configuro el bot de Discord?", [
        { ol: ["[discord.com/developers/applications](https://discord.com/developers/applications) → **New Application**.",
          "**Installation** → Install Link: **None** → guardar.",
          "**Bot** → desactiva **Public Bot** y activa **Message Content Intent** (para el puente de chat) → **Reset Token** → copiar.",
          "Panel: **Ajustes → Bot de Discord** → pega el token, actívalo, **Guardar**. Cuando ponga **Online**, haz clic en **Añadir el bot a tu Discord**.",
          "Escribe `/status` en Discord."] },
        "No compartas nunca el token del bot. Si se filtra, pulsa Reset Token otra vez."]],
      ["slash-commands", "discord", "El bot está conectado pero no salen los comandos con barra", [
        { ul: ["Los comandos nuevos pueden tardar un minuto. Reinicia Discord (Ctrl+R en el PC).",
          "Comprueba que en **Ajustes → Bot de Discord** el servidor de Discord donde responde el bot es el tuyo.",
          "`/start`, `/stop`, `/restart` y `/whitelist` solo aparecen a quien tiene **Gestionar servidor**, o a los usuarios de Discord que hayas permitido."] }]],
      ["alerts", "discord", "¿Puedo recibir un aviso cuando el servidor se cierra o alguien entra?", [
        "Sí, en el móvil (app gratis **ntfy**, **Ajustes → App para el móvil**), en Discord, Telegram, Slack y otras apps, o por correo. Elige qué quieres saber en **Avisarme de**. **Configuración → Avisos de entrada** publica cuando entran los jugadores que elijas."]],

      ["crash-lag", "trouble", "El servidor se cierra o va a tirones", [
        { ol: ["**Registros → Explicar todo el registro** lista cada error en lenguaje claro, incluidos mods rotos y falta de memoria.",
          "**Estado** muestra la memoria y el disco, y **Ajustes → Carga del equipo** tiene gráficas de 24 horas.",
          "En un ordenador antiguo, usa el preajuste **Ordenador lento**, baja el máximo de coches y activa el modo ligero."] },
        "Un servidor que se cierra se reinicia solo, y te avisa si tienes activados los avisos de cierre."]],
      ["undo", "trouble", "Cambié un ajuste y ahora algo no funciona", [
        "**Configuración → ¿Qué ha cambiado?** guarda las últimas 40 versiones de tu configuración, con quién cambió qué. **Comparar con ahora** muestra la diferencia, y **Restaurar** vuelve atrás. Tu AuthKey se conserva, y puedes deshacer lo deshecho."]],
      ["sleep", "trouble", "¿Tengo que tener el ordenador encendido 24/7?", [
        "No. **Ajustes → Suspensión y despertar** lo suspende cuando nadie ha jugado en un rato y lo despierta antes de los eventos. Con **Wake-on-LAN** (hace falta cable de red) tus amigos pueden despertarlo con `/start` en Discord o el botón **Despertar** de la app. La puntuación de compatibilidad indica qué falta por configurar."]],
      ["new-computer", "trouble", "¿Cómo paso mi servidor a otro ordenador?", [
        { ol: ["En el ordenador viejo: **Ajustes → Copia / mover a otro ordenador → Exportar ajustes + mods**.",
          "Instala EasyServer en el nuevo y luego **Importar…** ese archivo.",
          "Vuelve a pegar tu AuthKey: las claves y contraseñas nunca van en las exportaciones."] },
        "Las copias nocturnas están activadas por defecto, y puedes descargar las últimas 7 cuando quieras."]],
      ["get-help", "trouble", "Mi problema no está aquí. ¿Cómo consigo ayuda?", [
        { ol: ["**Estado → Descargar informe de diagnóstico**. Se le quitan las claves, contraseñas y direcciones.",
          "[Pregunta en el foro de la comunidad]({ASK}) y adjunta el informe. Los errores van a las [incidencias]({GH}/issues/new/choose)."] },
        "¿Has encontrado un problema de seguridad? Usa el [aviso privado]({GH}/security/advisories/new) en vez de publicarlo."]],
    ],
  },
};
