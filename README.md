<h1 align="center">PDF Lecture Concatenator</h1>

<p align="center">
  <b>Drop in a folder of lecture PDFs, get one PDF back — in the order you actually want.</b>
</p>

<p align="center">
  <img alt="install" src="https://img.shields.io/badge/install-one%20double--click-2b8a3e">
  <img alt="python" src="https://img.shields.io/badge/python-3.10%2B-3776ab">
  <img alt="node" src="https://img.shields.io/badge/node-18%2B-339933">
  <img alt="stack" src="https://img.shields.io/badge/stack-FastAPI%20%2B%20React-0b7285">
  <img alt="platform" src="https://img.shields.io/badge/runs%20on-Windows%20%7C%20macOS%20%7C%20Linux-555">
  <img alt="license" src="https://img.shields.io/badge/license-MIT-555">
</p>

---

## Install it

| Your machine | What to do |
|---|---|
| **Windows** | download the project and **double-click `Install.bat`** |
| **Linux / macOS / WSL** | `./install.sh` |

```bash
git clone https://github.com/semyonsw/pdf-concatinator.git
cd pdf-concatinator
./install.sh          # or: Install.bat on Windows
```

No Python of your own, no `pip`, no `npm`, no terminal on Windows. The installer:

- finds a usable Python and Node — and offers to install them if they're missing;
- keeps everything inside this folder (`.venv/`, `frontend/node_modules/`),
  touching nothing else on your machine;
- **explains, in plain English, anything that goes wrong, and fixes what it can
  fix by itself** — dropped downloads, intercepted certificates, a broken conda
  Python, a Python too new for its packages, npm peer-dependency conflicts;
- **runs the project's own test suite at the end**, so "install complete" means
  the code really works here, not just that files were copied;
- puts a **PDF Concatenator** shortcut on your Windows Desktop.

Re-running is safe: it repairs a half-finished install. Full detail and a
troubleshooting table: **[INSTALL.md](INSTALL.md)**.

---

## Use it

**Windows** — double-click **PDF Concatenator** on your Desktop.
**Linux / macOS** — `./run_web.sh`

Your browser opens on <http://localhost:5173>. Then:

1. **Add PDFs** — the button, or drag them onto the page.
2. **Sort them** — by lecture name (numeric-aware, so `9.4` comes before
   `10.2`), or by modified time, newest or oldest first.
3. **Build the queue** — add selected, add all, remove, clear, and drag rows
   (or use the ↑↓ buttons) until the order is right.
4. **Merge** — a progress bar runs while the server works.
5. **Download** the single merged PDF.

Keep the launcher window open while you work; closing it stops the app.

> Prefer no browser at all? **Start PDF Concatenator (desktop window).bat** —
> or `.venv/bin/python pdf_concatenator_gui.py` — opens the older single-window
> desktop version, which does the same merging.

---

## How it fits together

```
  browser (React, :5173)  ──HTTP──▶  FastAPI engine (:8000)  ──▶  pypdf
        drag, sort, queue                sessions, jobs            the merge
                                              │
                                       .web_data/<session>/
                                       uploads + merged output
```

| Path | What it is |
|---|---|
| [backend/app/main.py](backend/app/main.py) | the API: sessions, upload, merge jobs, download |
| [backend/app/core_logic.py](backend/app/core_logic.py) | the sorting, the unicode filename decoding, the merge |
| [backend/app/storage.py](backend/app/storage.py) | per-session file storage under `.web_data/` |
| [frontend/src/App.jsx](frontend/src/App.jsx) | the whole interface |
| [pdf_concatenator_gui.py](pdf_concatenator_gui.py) | the desktop (Tkinter) version |
| [tests/](tests/) | unit tests for the sorting/merging, API tests for the endpoints |

Uploaded and merged files never leave your machine: they sit in `.web_data/`
until you delete them. There is no account, no server, no telemetry.

### API

| Endpoint | Purpose |
|---|---|
| `POST /api/session` | start a session |
| `POST /api/upload?session_id=<id>` | upload one or more PDFs |
| `GET /api/files?session_id=<id>&sort_mode=name\|mtime_asc\|mtime_desc` | list them, sorted |
| `POST /api/merge` | start a merge job with an explicit queue order |
| `GET /api/merge/<job_id>?session_id=<id>` | poll progress |
| `GET /api/merge/<job_id>/download?session_id=<id>` | fetch the result |
| `GET /api/health` | health check |

---

## Working on it

```bash
.venv/bin/python -m uvicorn backend.app.main:app --reload --port 8000   # engine, auto-reload
npm --prefix frontend run dev                                           # interface, hot reload
.venv/bin/python -m pytest -q                                           # tests
VITE_API_URL=http://127.0.0.1:8001 npm --prefix frontend run dev        # point at another engine
```

On Windows use `.venv\Scripts\python.exe` instead of `.venv/bin/python`.

Good to know:

- Folder scanning is **not** recursive, on purpose.
- The numeric-aware sort keys on the first dotted number in the name, so
  `10.2` follows `9.4` instead of preceding it.
- Per-file upload cap: 120 MB (`MAX_FILE_SIZE_BYTES` in
  [backend/app/main.py](backend/app/main.py)).

---

## License

[MIT](LICENSE).
