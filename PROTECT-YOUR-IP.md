# Protecting your IP (and avoiding DDoS)

When you host a BeamMP server from home, players connect **straight to your home IP address**. This guide explains the risk and the easiest ways to protect yourself. None of this is required to play - it matters most for public servers.

## The risk, in plain terms

- Anyone who connects to your server can see your home IP with basic tools.
- With an IP, someone can pay a few dollars on a "booter" / "stresser" site to flood it - no skill needed.
- A home connection can't absorb a flood, so **your whole house's internet drops**, not just the game.

This is the main reason some people still pay for hosting: data-centre hosts sit behind DDoS protection that a home connection doesn't have.

The good news: you usually don't need to stop a flood - you just need to **not expose your home IP in the first place.** A relay (tunnel) does that by putting someone else's server in front of yours.

## The trade-off

| | Direct (default) | Through a relay |
|---|---|---|
| Chance of a DDoS hitting your home | Higher - your home IP is visible | **Much lower** - only the relay's address is visible |
| Lag | Lowest | **Higher** - usually +10-40 ms with a relay in your country, more if it's far away |
| Setup | Port forward on your router | A relay (see below), no router port forward |

## Built into EasyServer: Settings → Hide your IP

Both features are **off by default**. Turn them on in the dashboard under **Settings → Hide your IP (DDoS protection)**.

**Hide my IP** - once you have a relay (options below), enter its address and port. Then:

- the dashboard, Discord join alerts and the network check give players the **relay address**, never your home IP
- **Test the relay** checks that the relay really reaches your server and shows roughly how long the detour takes
- the **Network** page warns you if your home address can still be reached directly (router port forward still on) or shows up in the public server list

When you turn it on:

1. **Remove the port forward** for the game port (30814) from your router - otherwise attackers can still reach your home directly.
2. **Make the server private** (Config → Private server) and give players the relay address. The BeamMP server list shows the address the server reports from, which with most relays is still your home IP. (If *all* of this computer's traffic goes through the relay - a full VPN or WireGuard tunnel - the list shows the relay's address instead; the network check tells you which.)
3. **If your home IP was already shared, restart your router.** Most providers give you a new address after a restart.
4. If **Access from the internet** (remote dashboard) is on, the dashboard is still reachable at your home address - turn it off if you don't need it.

**Flood protection** (Linux only) - limits how fast one address can connect to your game server (about 20 new connections a minute) and how many packets it can send (about 1000 a second). Normal players never get near that; one computer flooding your server gets cut off, and the dashboard raises a security alert. Your home network and a relay app running on the same computer are never limited. It **can't stop a big DDoS** - that fills your internet line before it ever reaches your computer - so it's an extra layer, not a replacement for hiding your IP.

## Getting a relay

### Option 1 - playit.gg (easiest)

[playit.gg](https://playit.gg) is built for game servers and gives players a public address that hides your real IP.

- BeamMP needs **both TCP and UDP** on port 30814.
- playit's free tier covers UDP, but **TCP now needs playit premium**, so a full BeamMP tunnel requires the paid plan.
- Install the playit app on the same computer as the server and make a TCP+UDP tunnel to local port 30814.
- Put the address and port playit gives you into **Settings → Hide your IP**.
- See playit's own BeamNG/BeamMP guide: https://playit.gg/support/playit-beamng-beammp-server/

### Option 2 - a VPN with port forwarding

A normal VPN only hides your *outgoing* traffic. To host a server, players have to connect *in*, so the VPN must offer **port forwarding** - and many big VPNs (NordVPN, Surfshark, ...) don't. Some that do: Proton VPN, Private Internet Access (PIA), PureVPN. Mullvad removed it in 2023.

Things to know:

- The VPN usually picks the port for you, and it can **change when the VPN reconnects** - update it in Settings (and tell your players) when it does.
- The VPN's address shows up in the server list, because all your traffic goes through it.
- Everything you do on that computer gets the extra lag, not just the game server.

### Option 3 - your own VPS with WireGuard (most control)

Rent a small VPS (about €3-5/month) close to you and your players, run **WireGuard** on it, and forward port 30814 (TCP and UDP) from the VPS through the tunnel to your PC. Attacks then hit the VPS - which has DDoS protection - instead of your house.

- The address never changes, and it's often cheaper than full game-server hosting.
- The VPS only relays traffic - the game still runs on your PC.
- It's the most work to set up; follow a "WireGuard port forwarding" guide for your VPS provider. Then enter the VPS's IP in **Settings → Hide your IP**.

## Other things that help

- **Restart your router after an attack.** Most home connections get a new IP address when the router restarts, so the attacker loses track of you. Only share the new address through a relay.
- **Keep the server private / invite-only** (`Private = true`, or the allow-list in the dashboard) if you only play with friends, and **never paste your IP** in public Discord servers, forums or screenshots.
- **OpenWrt (or another good router firmware)** lets you rate-limit connections, block port scans and keep your home's internet usable under load (SQM). It's a nice extra layer, but it **can't stop a real DDoS** either - the flood fills your line before it reaches the router - and it doesn't hide your IP.
- Turn on EasyServer's **security alerts** so you're warned about floods and password guessing.

---

*Not affiliated with the BeamMP team. Relay and VPN services mentioned here are third-party; check their terms and pricing yourself.*
