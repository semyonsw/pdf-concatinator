# Installing the PDF Lecture Concatenator

The short version:

| Your machine | What to do |
|---|---|
| **Windows** | double-click **`Install.bat`** |
| **Linux / macOS / WSL** | `./install.sh` |

Everything below is only here for when that does not work.

---

## What the installer actually does

1. Checks the OS and finds a Python 3.10+ that is **actually usable** — it
   rejects a Python whose `ssl`, `sqlite3` or `venv` module is broken (a common
   state for Anaconda/Miniconda installs), because such a Python cannot download
   packages. On Windows it offers to install Python 3.12 for you via `winget`.
2. Creates a private environment in `.venv/`, so nothing is installed
   system-wide and nothing clashes with your other Python projects.
3. Installs [requirements.txt](requirements.txt), retrying automatically with a
   longer timeout, then relaxed certificate checks, then pre-built wheels only.
4. Imports every package to prove the install works, and warns (without failing)
   if `tkinter` is missing — that only affects the optional desktop window.
5. Finds Node.js 18+ and installs the browser interface with `npm ci`, falling
   back to `npm install` and then `--legacy-peer-deps`.
6. Builds the interface once, to catch a broken toolchain now rather than later.
7. **Runs the project's own test suite** — so "install complete" means the code
   actually works on your machine, not just that files were copied.
8. Windows: writes the two launchers and puts a *PDF Concatenator* shortcut on
   your Desktop and in the Start menu.

Everything is logged to `install.log`. Re-running is safe and repairs a
half-finished install. Nothing is written outside this folder except the
Windows shortcuts.

---

## Running it a different way

| Situation | Command |
|---|---|
| Windows, normal | double-click `Install.bat` |
| Windows, from a terminal | `powershell -ExecutionPolicy Bypass -File tools\install.ps1` |
| Windows, no questions | `powershell -ExecutionPolicy Bypass -File tools\install.ps1 -NonInteractive` |
| Linux / macOS / WSL | `./install.sh` |

---

## Troubleshooting

The installer prints the cause and the fix for anything it recognises. Same
information, for reference:

| Message | What it means | Fix |
|---|---|---|
| *Python 3.10 or newer was not found* | No usable Python | Windows: let the installer fetch 3.12. Linux: `sudo apt install python3 python3-venv python3-pip` |
| *this Python has no 'venv' module* | Debian/Ubuntu splits it out | `sudo apt install python3-venv` |
| *…but its SSL support is broken* | conda Python without its OpenSSL DLLs | `conda install -y openssl`, or install a normal python.org Python |
| *no ready-made build of `<package>` exists for this Python version* | Python newer than the packages | On Windows the installer fetches 3.12 and retries by itself; otherwise install 3.12, delete `.venv/`, re-run |
| *a package had to be compiled and the C build tools are missing* | Source-only wheel | `sudo apt install build-essential python3-dev`, or on Windows install [Build Tools for VS](https://visualstudio.microsoft.com/visual-cpp-build-tools/) |
| *the HTTPS connection to pypi.org could not be verified* | Proxy/antivirus intercepting TLS | `export HTTPS_PROXY=http://proxy:8080` (Windows: `set`), re-run |
| *Node.js 18 or newer is required* | No Node | Windows: the installer offers to fetch the LTS. Linux: `nvm install --lts` |
| *two packages asked for conflicting dependency versions* | ERESOLVE | Already retried with `--legacy-peer-deps`; if it persists delete `frontend/node_modules` and `frontend/package-lock.json`, re-run |
| *npm could not write into the project folder* | Permissions, or OneDrive syncing | Don't use `sudo`; pause OneDrive while installing |
| *tkinter is missing* | Optional desktop window unavailable | `sudo apt install python3-tk`. The browser interface is unaffected |
| *some of the project tests failed* | Install worked, code has a problem | Read the end of `install.log`; open an issue with it attached |

### It installed, but nothing opens

**"The engine did not start"** — something else is already using port 8000:

```bat
netstat -ano | findstr :8000        :: Windows
ss -ltnp | grep :8000               ## Linux
```

Close it, or run the engine on another port and point the interface at it:

```bash
.venv/bin/python -m uvicorn backend.app.main:app --port 8001
VITE_API_URL=http://127.0.0.1:8001 npm --prefix frontend run dev
```

**The browser opens but every action fails** — the engine died. Its log is
`.web_data/backend.log` (Linux) or the minimised *engine* window (Windows).

**Uploads fail on large files** — the per-file cap is 120 MB, set by
`MAX_FILE_SIZE_BYTES` in [backend/app/main.py](backend/app/main.py).

### Starting over from scratch

```bash
rm -rf .venv frontend/node_modules frontend/dist install.log      # Linux/macOS
./install.sh
```

```bat
rmdir /s /q .venv frontend\node_modules                           :: Windows
Install.bat
```

Your merged files and uploads live in `.web_data/` and are left alone. Delete
that folder too if you want a truly clean slate.

---

## Uninstalling

Nothing is installed system-wide:

1. Delete the *PDF Concatenator* shortcuts from your Desktop and Start menu.
2. Delete this folder.
