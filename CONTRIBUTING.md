# Contributing to BeamMP EasyServer

Thanks for helping! Bug reports, ideas and code are all welcome.

## Reporting a bug

[Open a bug report](https://github.com/Csabika-dev/beammp-easyserver/issues/new/choose) and, if you can, attach a **diagnostic report**: dashboard → **Health** → **Download diagnostic report**. It contains the health checks, settings and recent log lines, with your keys, passwords and addresses removed. Have a quick look before posting anyway.

**Security problems** go to private reporting instead - see [SECURITY.md](SECURITY.md).

## How the project is put together

| Folder | What's in it |
|---|---|
| `dashboard/dashboard.py` | The web dashboard: one Python file, standard library only (no packages to install) |
| `dashboard/webui.html` | The dashboard's page (HTML, CSS and JavaScript in one file) |
| `dashboard/EasyServerStats/main.lua` | The plugin that runs inside the BeamMP server (Lua 5.3): stats, moderation, chat commands |
| `dashboard/modscan.py` | The mod virus check |
| `linux/` | Linux installer and `control.py`, the small root helper the dashboard asks for admin jobs |
| `windows/` | Windows installer and scripts (PowerShell; the `.ps1` files use Windows line endings) |
| `wake/` | The optional wake helper for an always-on device at home |
| `android/` | The Android app |
| `tests/` | Automated tests |
| `docs/` | The project website (GitHub Pages) |

## Running the tests

You need Python 3.10 or newer and, for the plugin tests, Lua 5.3 (`sudo apt install lua5.3`). Nothing else - no install, no admin rights, no BeamMP server:

```bash
python -m unittest discover -s tests -v
```

The tests start the real dashboard in a temporary folder with a fake root helper, then attack it: every page without logging in, CSRF, wrong passwords, moderator and viewer accounts, hostile file names, internal webhook addresses, script injection on the status page, leaked keys. They also run the game plugin against a fake BeamMP server and check that the root helper refuses bad requests.

They run automatically on GitHub for every push and pull request (Linux and Windows). A red ✗ next to a commit means a test failed - click it to see which one.

## Making changes

- **Keep it simple for the people using it.** Dashboard text is plain English without jargon; every new setting explains what it does in one line.
- **Safe by default.** New features that open something up start switched off. Anything that can change the network asks first.
- **Standard library only** for the dashboard and helpers, so nobody has to install or update packages.
- **Add a test** for anything that handles files, user input, logins or talks to other services. If you fix a security problem, add a test that would have caught it.
- Update `CHANGELOG.md` and, for new features, the guides in `README.md`.
