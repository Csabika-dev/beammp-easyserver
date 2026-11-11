# Protecting your IP (and avoiding DDoS)

When you host a BeamMP server from home, players connect **straight to your home IP address**. This guide explains the risk and the easiest ways to protect yourself. None of this is required to play - it matters most for public servers.

## The risk, in plain terms

- Anyone who connects to your server can see your home IP with basic tools.
- With an IP, someone can pay a few dollars on a "booter" / "stresser" site to flood it - no skill needed.
- A home connection can't absorb a flood, so **your whole house's internet drops**, not just the game.

This is the main reason some people still pay for hosting: data-centre hosts sit behind DDoS protection that a home connection doesn't have.

The good news: you usually don't need to stop a flood - you just need to **not expose your home IP in the first place.** A tunnel does that by putting someone else's server in front of yours.

## Option 1 - playit.gg (easiest)

[playit.gg](https://playit.gg) is built for game servers and gives players a public address that hides your real IP.

- BeamMP needs **both TCP and UDP** on port 30814.
- playit's free tier covers UDP, but **TCP now needs playit premium**, so a full BeamMP tunnel requires the paid plan.
- Once set up, give players the **playit address**, never your real IP.
- See playit's own BeamNG/BeamMP guide: https://playit.gg/support/playit-beamng-beammp-server/

## Option 2 - a cheap VPS (more control)

Rent a small VPS (about €3-5/month) and run a tunnel through it. Attacks then hit the VPS, which has DDoS protection, instead of your house.

- More setup than playit, but you control it and it's often cheaper than full game-server hosting.
- The VPS only relays traffic - the game still runs on your PC, so your hardware does the work.

## Option 3 - just be careful (free, partial)

If you only play with people you trust, these habits go a long way:

- Keep the server **private / invite-only** (`Private = true` in `ServerConfig.toml`, or use the allow-list in the dashboard).
- **Never paste your IP** in public Discord servers, forums or screenshots.
- Consider **changing the default port** from 30814.
- Turn on EasyServer's **security alerts** so you're warned about connection floods and password guessing.

These don't stop a determined attacker who's already in your server, but they cut off the easy cases.

## What EasyServer does and doesn't do

EasyServer **can't** stop a DDoS for you - that needs a large network in front of your connection, which is exactly what a home setup lacks. What it does help with:

- **Security alerts** warn you about connection floods, password guessing and probing.
- Login lockouts and the virus check protect the dashboard and your mods.

For hiding your IP, use a tunnel (Option 1 or 2) - that's the part that actually protects your home connection.

---

*Not affiliated with the BeamMP team. Tunnel services linked here are third-party; check their terms and pricing yourself.*
