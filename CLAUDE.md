# Ludotek — portable game library manager

Ludotek (from the French *ludothèque*, a game library) is a tool that **lives inside a PC games folder** and presents it as a library: it scans the folder, works out the state of each item (installed folder, archive to extract, executable), cleans up names, spots duplicates, watches for additions and removals, and lets you launch games, annotate them, and attach a cover and a description.

## Non-negotiable constraints

- **Small layout**: the `ludotek/` package (one module per concern, entry point `ludotek/__main__.py`) + `ludotek/web/` (HTML, CSS, JS, fonts and translation catalogs of the UI). Tests in `tests/`, build files in `script/`, design doc in `docs/`, release-please config in `.github/`. Keep it flat: no sub-packages, no extra layers unless needed.
- **Standard library only** (Python 3.8+). No pip dependency at runtime. No front-end framework, no build step, no CDN: everything must work offline.
- **Portable**: all library data lives in the watched folder, never in the user profile. The only exception is `.ludotek.json` (watched folder and language), stored next to the app (`APP_DIR`).
- **Language**: code, comments, docstrings and docs are in English. Everything the user sees (UI, server error messages shown in toasts, console banner and logs) is **translated**: English and French today, one JSON catalog per language in `ludotek/web/i18n/`. Never hard-code a user-facing string: add a key to **every** catalog and use `t()` (Python `ludotek.i18n.t`, JS `t` / `tn`). Default language: saved setting, else system language, else English.
- **End user on Windows**, without Python installed: the app ships as an `.exe` built with PyInstaller. Development happens on **WSL (Linux)**: the code must stay cross-platform (`os.startfile` on Windows, `open` on macOS, `xdg-open` on Linux).

## Running in dev

```bash
python3 -m ludotek /mnt/d/Jeux            # from the repo root; folder to watch (default: saved setting, else the repo root)
python3 -m ludotek /mnt/d/Jeux --no-browser
LANG=fr_FR.UTF-8 python3 -m ludotek /mnt/d/Jeux   # try another system language (a saved "language" setting wins)
```

Interface: `http://127.0.0.1:8765/` (random fallback port if 8765 is taken).

On WSL, "Play" and "Open location" go through `xdg-open` and therefore do not open Windows apps. To really test these actions, run the script with Windows Python (`python.exe -m ludotek`) or test the built `.exe`.

## Building the Windows executable

PyInstaller does not cross-compile: the build must run **on Windows** (Windows Python or CI with a Windows runner).

```
python -m pip install pyinstaller
.\script\build.ps1                            # -> dist\Ludotek.exe
```

- `script/ludotek.spec` is the **only** place for build settings (entry, name, data files, console window). Paths in it are built from `ROOT = dirname(SPECPATH)`: never commit absolute paths. Both scripts just run it with `--distpath dist --workpath build`.
- **CI**: `.github/workflows/build-exe.yml`, on every push to `main` (and manually). Job `release-please` keeps the release PR up to date; job `build` (Windows runner) runs `python -m pytest -q`, then `script/build.ps1`, smoke-tests the exe (page, UI files, fonts, scan, Quit) and uploads it as an artifact; when a release was just created, `build` first checks the tag equals `v` + `ludotek.__version__` and job `attach` uploads `Ludotek.exe` to that release. All in one workflow on purpose: tags created with `GITHUB_TOKEN` do not trigger other workflows. Stable download link: `releases/latest/download/Ludotek.exe`. Keep the PyInstaller and pytest versions pinned there. Repo setting required: Settings > Actions > General > "Allow GitHub Actions to create and approve pull requests".
- **Versioning**: semver driven by commit messages ([Conventional Commits](https://www.conventionalcommits.org)) through release-please (`.github/release-please-config.json`, `.github/.release-please-manifest.json`, `release-type: simple`, `bump-minor-pre-major`). The version lives in `version.txt`, the manifest and `__version__` in `ludotek/__init__.py` (line annotated `x-release-please-version`): only the release PR changes them, never edit by hand. It is shown in the console banner and the UI header (`__VERSION__` in `index.html`, replaced like the token). Never reuse or move a published tag.
- `script/build.sh` is for Git Bash on Windows; on Linux/WSL it produces a Linux binary (handy to check that `ludotek/web` is bundled, useless for end users).
- `datas` must include `ludotek/web`: without it the exe starts but serves no page. `pathex` must include the repo root, since the entry script imports `ludotek` absolutely.
- The exe opens a **console window on purpose** (`console=True`): closing it, Ctrl+C or the UI's "Quit" button stops the server. Without it the server would keep running invisibly after the browser tab is closed. Keep the "Quit" button. Closing the window kills the process without calling `save_db()`, which is fine because every change is already saved when it happens. `config.FROZEN`/`APP_DIR` handle the `sys.frozen` case, and the exe's own name is added to `IGNORED`.

## Architecture

```
ludotek/
  __main__.py         entry point: main() sets up logging, opens the server, prints the banner, runs the first scan, starts the worker threads
  __init__.py         __version__ (bumped by release-please)
  config.py           paths (ROOT, DB_PATH, COVERS_DIR, WEB_DIR), settings file (load/save_settings), set_root, LANGUAGE, port, token, limits, file types, IGNORED
  i18n.py             t(key, n=, **params), number, catalog, system_language, resolve, page_data (sets config.LANGUAGE at import)
  names.py            clean_name, match_key, detect_source, item_id + their regexes
  storage.py          DB, LOCK, PREV_SEEN, reload, save_db
  scanner.py          scan, entry_kind, measure_dir, worker, rescan_loop, reset, CURRENT, PENDING, WORK + EXE_BLACKLIST, SKIP_DIRS
  covers.py           sniff_image, fetch_image, read_cover, set_cover, clear_cover
  system.py           open_path, reveal_path (per OS), pick_folder (tkinter dialog)
  api.py              payload() + POST actions (ACTIONS table, UPDATABLE whitelist, ApiError)
  server.py           Handler: Host/token checks, static files (STATIC), routing to api.ACTIONS
  web/                index.html, style.css, app.js, fonts/ (bundled woff2 + OFL licenses), i18n/ (en.json, fr.json)
tests/
  test_i18n.py        catalog consistency + i18n rules (pytest)
```

Dependencies go one way: `config` <- `i18n` <- `names`, `storage` <- `scanner`, `covers`, `system` <- `api` <- `server` <- `__main__`. HTTP details stay in `server.py`; `api.py` never touches the request handler.

- **Names**: `clean_name` turns a file name into a readable title (strips release tags, `[...]`, `(...)`, `_` and `-` between words). `match_key` produces a normalized key to detect duplicates (without edition words or single letters). `detect_source` identifies the source from the name.
- **Storage**: `DB` is a dict loaded from `.bibliotheque.json`. `save_db()` writes atomically (`.tmp` file then `os.replace`) and only if the content changed. Every read or write of `DB`, `CURRENT` or `PENDING` happens under `LOCK` (RLock).
- **Scan**: `scan()` reads the top level of the folder, then updates `CURRENT` and `DB` (vanished items moved to `DB["removed"]`, and restored if they come back). Folders whose `mtime` changed are queued for `worker()`, which computes the size and the list of executables via `measure_dir` (depth ≤ 3, sorted by increasing depth then decreasing size). `rescan_loop()` runs a scan every `RESCAN_EVERY` seconds.
- **Module state**: `config.ROOT`, `config.DB_PATH`, `config.COVERS_DIR`, `config.LANGUAGE`, `storage.PREV_SEEN` and `scanner.LAST_SCAN` are reassigned at runtime, so always read them through their module (`config.ROOT`), never via `from .config import ROOT`. `DB`, `CURRENT` and `PENDING` are only mutated in place, so importing them directly is fine.
- **Watched folder**: chosen at start (command line, then `.ludotek.json` if the folder still exists, then `APP_DIR`) and changeable from the UI (`api.settings`): under `LOCK` it saves the old DB, calls `config.set_root`, `storage.reload`, `scanner.reset`, then scans. `scan()` and `worker()` remember the root they started with and drop their results if it changed meanwhile.
- **Covers**: `sniff_image` validates the format from the bytes (PNG/JPG/GIF/WEBP), `fetch_image` downloads from an http(s) URL, and `set_cover` / `clear_cover` manage the `.bibliotheque/covers/<id>.<ext>` files.
- **API**: each POST action is a function `(iid, req) -> dict` registered in `api.ACTIONS`; `req` is `{"raw", "type", "json"}` (`json` is always a dict). Errors shown to the user are raised as `ApiError(status, t("error.…"))` (already translated; raw OS messages pass through as is). `quit` is handled in `server.py` because it stops the server.
- **UI** (`ludotek/web/`): grid rendered in vanilla JS. The token is injected into `index.html` (`<meta name="biblio-token">`, replacing `__TOKEN__`) and read by `app.js`. So are `__LANG__` (`<html lang>`) and `__I18N__` (current catalog + English fallback + language list, JSON in `<script id="i18n">`, `</` escaped): `index.html` holds no text, only `data-i18n`, `data-i18n-placeholder|title|aria-label` keys applied by `applyI18n()`. Changing the language in Settings saves it and reloads the page. Sorting, dates and sizes use `LANG` (`Intl`, `localeCompare`) and the catalog's `size.units`. The UI polls `/api/library` every 4 s and only re-renders if the JSON changed. The details dialog does not overwrite a focused `textarea`.

## Data

`.bibliotheque.json`:

```jsonc
{
  "items":   { "<id>": { "file", "first_seen", "favorite", "status", "notes", "description",
                         "exe", "exes", "size", "size_mtime", "last_launched", "cover", "cover_v" } },
  "removed": { "<id>": { ...same structure..., "removed_at" } },
  "last_seen_at": 1793097041.5
}
```

`.ludotek.json` (next to the app, not in the watched folder): `{"root": "D:\\Jeux", "language": "fr"}`. Unknown keys are kept when saving, so new settings can be added there.

- `id` = first 12 hex characters of the SHA-1 of the file name. Renaming a file therefore creates a new item; the old one moves to `removed`.
- "New" = `first_seen > last_seen_at` of the previous session (`PREV_SEEN`).
- `DB` fields must stay backward compatible: always read with `.get(...)` and a default, never rename an existing key without a migration. Same for the data file and folder names (`.bibliotheque.json`, `.bibliotheque/`): existing libraries depend on them.
- Anything starting with `.` at the root is ignored by the scan (`.bibliotheque.json`, `.bibliotheque/`). The `ludotek/` package folder and the exe's own name are excluded via `IGNORED`.

## Endpoints

| Method | Route                | Purpose                                                       |
| ------ | -------------------- | ------------------------------------------------------------- |
| GET    | `/`                  | HTML page (`__TOKEN__`, `__VERSION__`, `__LANG__`, `__I18N__` injected) |
| GET    | `/app.js`, `/style.css`, `/fonts/*.woff2` | UI files and fonts (fixed list in `server.STATIC`) |
| GET    | `/api/library`       | Full state: `root`, `items`, `removed`                        |
| GET    | `/covers/<id>.<ext>` | Cover image (name validated by `COVER_NAME_RE`)               |
| POST   | `/api/rescan`        | Immediate scan                                                |
| POST   | `/api/update/<id>`   | JSON with `favorite`, `status`, `notes`, `description`, `exe` |
| POST   | `/api/launch/<id>`   | Launches the game, archive or executable                      |
| POST   | `/api/reveal/<id>`   | Opens the location in the file explorer                       |
| POST   | `/api/cover/<id>`    | Binary `image/*` body **or** JSON `{"url": "https://..."}`    |
| POST   | `/api/uncover/<id>`  | Removes the cover                                             |
| POST   | `/api/settings`      | JSON `{"root": "D:\\Jeux", "language": "en"}` (both optional, validated first): switches folder and/or language and saves them |
| POST   | `/api/browse`        | Opens the native folder dialog, returns `{"path": ... or null}` |
| POST   | `/api/quit`          | Stops the server                                              |

## Security (must be preserved)

- Listens on **127.0.0.1 only**, never `0.0.0.0`.
- Every `POST` requires the `X-Biblio-Token` header. Since it is a custom header, the browser must send a preflight, which blocks third-party sites that would try to launch executables. The server does not answer `OPTIONS` and sends no CORS headers: keep it that way.
- `Host` header check (`127.0.0.1` / `localhost`) against DNS rebinding.
- Paths always come from `DB` or `CURRENT` via an `id`, never directly from user input. Cover names are validated by regex. The one exception is the watched folder (`/api/settings`): token-protected, must be an absolute path to an existing folder.
- Images are limited to 15 MB (`MAX_IMAGE`) and validated by their bytes, not by their extension or Content-Type.
- In the UI, all dynamic text, translations included, goes through `esc()` before being inserted into HTML.

## Testing

Automated: `python -m pytest -q` (`tests/`, pytest, dev only; CI runs it before the build). `tests/test_i18n.py` checks that every catalog has the same keys and placeholders, that every key used in `index.html`, `app.js` and `ludotek/*.py` exists and every catalog key is used (so use **literal** keys, never build them by concatenation), plus plural, fallback and language detection rules.

Manual procedure for the rest:

1. Create a fake games folder:
   - subfolders with small dummy `.exe` files (including `unins000.exe`, `UnityCrashHandler64.exe` and `redist/vcredist.exe`, which must be ignored);
   - `.rar`, `.zip` and `.exe` files with realistic names (`Jeu-SteamRIP.com.rar`, `Jeu [FitGirl Repack].rar`…).
2. Run with `--no-browser` and query the API with `curl` or `urllib`:
   - cleaned names, `kind`, detected `exe`, duplicates;
   - `POST` without token: must return 403;
   - delete a file then rescan: it must appear in `removed`;
   - upload a valid PNG (200) and a fake PNG (400);
   - `/covers/../...` must return 404.
3. Check the UI headless with Playwright in **both languages** (system `LANG=en_US.UTF-8` / `fr_FR.UTF-8`, or the Settings selector): card rendering, details dialog, search, no raw key visible, and **no console errors**.
4. Check the JS syntax: `node --check ludotek/web/app.js`.

New tests go in `tests/` (pytest), never as a runtime dependency of the app.

## Conventions

- **Commit messages: Conventional Commits**, they decide the next version. `fix:` (patch), `feat:` (minor), `feat!:` or a `BREAKING CHANGE:` footer (breaking; only minor while < 1.0), and `docs:`, `refactor:`, `test:`, `ci:`, `chore:`, `build:` for no release. Subject in English, imperative, lowercase after the type. With squash merges, the PR title is the commit message.
- Python code: short functions, comments and docstrings in English, no unnecessary classes.
- Logging: `log = logging.getLogger(__name__)` per module, configured once in `__main__.py` (`setup_logging`, translated level names set at startup, stdout). Messages through `t("log.…")`. Log events and errors (scan changes, folder analysis, actions, failed or refused requests), never the 4 s polling of `/api/library`; a repeating error is logged once (see `scanner._last_error`). Use `print` only for the startup banner.
- Do not block the HTTP thread on long operations: heavy disk work goes through `WORK` and `worker()`. Tolerated exceptions: downloading a cover from a URL (20 s timeout) and the native folder dialog (`/api/browse`, waits for the user; one at a time).
- Any new per-game data goes in `DB["items"][id]`, is exposed in `api.payload()` and, if editable, gets an entry in `api.UPDATABLE` (cleaning rule with type and size limit).
- New `POST` endpoint: write the function in `api.py` and add it to `api.ACTIONS`. The token and Host checks already run at the top of `do_POST`.
- New UI file: add it to `server.STATIC` (never serve paths built from the request).
- UI: follow `docs/DESIGN.md` (light theme, `--dp-*` tokens in `:root`, bundled fonts, blue reserved for meaningful emphasis). Layout usable from 380 px wide; check 1280 / 760 / 380 px renders after visual changes, in English and French (English labels are often longer).

## Ideas under consideration

- Planned work (automatic covers via the Steam store search, controller / TV mode) is detailed in `.local/plan.md` when present (local notes, not committed).
- On WSL, detect the environment and use `explorer.exe` / `cmd.exe /c start` to really launch Windows apps.
- Possible port to a native stack (Godot or C#/Avalonia) that produces a Windows `.exe` from Linux. The cleanup, duplicate and executable-detection logic is the part to keep as-is.
