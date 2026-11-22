import { Features } from "./Features.jsx";
import { Help } from "./Help.jsx";
import { Home } from "./Home.jsx";

export const PAGES = [
  { id: "home", file: "index.html", Page: Home,
    title: "BeamMP EasyServer - host a BeamNG.drive multiplayer server in one click",
    description: "Free one-click installer and web dashboard for BeamMP (BeamNG.drive multiplayer) servers on Windows and Linux. Mods with virus check, player stats, moderation, Discord, phone app.",
    ogTitle: "BeamMP EasyServer",
    ogDescription: "Host your own BeamNG.drive multiplayer server in one click - and run it from your phone." },
  { id: "features", file: "features.html", Page: Features,
    title: "Features - BeamMP EasyServer",
    description: "What BeamMP EasyServer does: guided setup, a dashboard you can use from your phone, virus-checked mods, vehicle rules, server plugins and team accounts. Free for Windows and Linux.",
    ogTitle: "BeamMP EasyServer - features",
    ogDescription: "Host a BeamMP server for your friends without editing config files." },
  { id: "help", file: "help.html", Page: Help,
    title: "Help &amp; community - BeamMP EasyServer",
    description: "Answers to the most common BeamMP EasyServer questions: friends can't join, port forwarding, mods, slow joining, forgotten password, Discord bot, crashes. Ask the community if yours isn't here.",
    ogTitle: "BeamMP EasyServer - Help &amp; community",
    ogDescription: "Common questions with ready answers, and a community forum for everything else." },
];
