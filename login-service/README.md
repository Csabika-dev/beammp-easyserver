# Sign in with Discord - the small helper service

Team members of an EasyServer dashboard can sign in with Discord instead of typing a password. Two things make that
hard for a program that runs on everyone's own computer:

- Discord only sends people back to addresses registered in advance, and every dashboard has its own address.
- The Discord app has a secret, and a secret can't be put in open-source code.

So this tiny service (one file, `worker.js`, running on Cloudflare Workers) does the Discord part and nothing else.
It **stores nothing** - no database, no list of users, no logs of who signed in.

## How it stays safe

1. When the owner turns the feature on, the dashboard asks the service for an id and a key. The key is
   `HMAC(MASTER_KEY, id)`, so only the service and that dashboard know it. The dashboard keeps it encrypted.
2. "Sign in with Discord": the dashboard signs *where to come back to* (its own address - never an address someone
   typed), plus a one-time code that is also stored in that browser as a cookie.
3. Discord asks the person to confirm, then the service asks Discord who it is, gives the access back to Discord
   straight away, and sends the browser back to the signed address with a note: "Discord user 1234…", signed with
   the dashboard's key, valid for 5 minutes.
4. The dashboard checks the signature, that the note is for this dashboard, this address and *this browser's*
   one-time code, and that a team account is linked to that Discord user. Two-step login and the
   "from the internet" rules apply as with a password. The owner always uses the password.

A note that ends up in another browser, at another address or another dashboard is useless. If someone ever took
over this service, they could not get into a dashboard by itself - they would also need the person's two-step code
where it's on - so keep two-step login on for accounts that may log in from the internet (it's required there anyway).

## Setting it up (project maintainers)

1. **Discord** - [discord.com/developers/applications](https://discord.com/developers/applications) → your app →
   **OAuth2** → **Redirects** → add `https://<your-worker-address>/cb` → **Save**. Copy the **Client Secret**
   (Reset Secret if you can't see it).
2. **Cloudflare** → **Workers & Pages** → **Create** → **Create Worker** → name it (e.g. `easyserver-login`) →
   **Deploy** → **Edit code** → replace everything with `worker.js` → **Deploy**.
3. The Worker → **Settings** → **Variables and secrets** → add:
   - `DISCORD_CLIENT_ID` (Text) - the Application ID
   - `DISCORD_CLIENT_SECRET` (Secret) - the Client Secret
   - `MASTER_KEY` (Secret) - a long random string (40+ characters). Changing it turns the feature off on every
     dashboard until the owner switches it on again.
4. Open `https://<your-worker-address>/` - it should say "EasyServer sign-in".
5. Put the address in `LOGIN_SERVICE` in `dashboard/dashboard.py` (now: `https://easyserver-login.easyserver-hq.workers.dev`).
6. Turn **Logs** off under the Worker's **Settings → Observability**, so no requests are kept.

Test: `node tests/login_service.test.mjs` runs the whole flow against a fake Discord.
