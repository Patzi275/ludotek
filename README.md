<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/logo-dark.png">
    <img src="assets/logo.png" width="96" height="96" alt="Ludotek">
  </picture>
</p>

# Ludotek

*From the French* ludothèque, *a game library.*

A portable game library for a folder of PC games. Drop `Ludotek.exe` next to your games and it turns the folder into a browsable library. Nothing to install, it works offline, and it never writes to your user profile.

Available in English and French. Ludotek picks your system language and you can switch in **Settings**.

## Features

- Scans the folder and tells installed games, archives to extract and installers apart.
- Cleans release names (`Hollow-Knight-SteamRIP.com` → *Hollow Knight*) and flags likely duplicates.
- Finds the right executable in each game folder, skipping uninstallers, redistributables and crash handlers.
- Launches games and opens their location.
- Favorites, status, notes, description and cover art (file, URL, drag and drop or paste).
- Watches for added and removed items, and lets you switch to another games folder from the settings.
- English and French interface, errors and console, with your system language by default.

## Usage

1. Download `Ludotek.exe` from the [latest release](../../releases/latest).
2. Put it in your games folder and run it, or choose another folder later in **Settings**.
3. The library opens in your browser. The console window logs what Ludotek does; close it (or click **Quit**) to stop the app.

Library data is stored in the games folder itself (`.bibliotheque.json`, `.bibliotheque/`). The chosen folder and language are remembered in `.ludotek.json`, next to the exe.

## From source

Requires Python 3.8+, standard library only.

```bash
python3 -m ludotek "D:\Jeux"         # from the repo root; no argument: saved folder, else the repo root
python3 -m ludotek --no-browser
```

Tests: `pip install pytest`, then `python -m pytest -q`.

**Adding a language**: copy `ludotek/web/i18n/en.json` to `<code>.json` (ISO 639-1, e.g. `es.json`), translate the values (keep the keys and `{placeholders}`), set `language.name`, `number.decimal`, `size.units` and `plural.zero_is_one`. For Windows to pick it up as the system language, add its code to `_WIN_LANGS` in `ludotek/i18n.py` (already there: de, en, es, fr, it, pt). The tests check the new catalog is complete.

Build the exe on Windows: `pip install pyinstaller`, then `.\script\build.ps1` (output: `dist\Ludotek.exe`). Every push to `main` also builds it in CI.

**Releasing**: write [Conventional Commits](https://www.conventionalcommits.org) (`fix:` → patch, `feat:` → minor, `feat!:` → breaking). [release-please](https://github.com/googleapis/release-please) keeps a release PR open with the next version and `CHANGELOG.md`; merging it tags `vX.Y.Z`, publishes the release and CI attaches `Ludotek.exe`.

## Roadmap

Automatic covers and a controller-friendly TV mode.

## Security

The server only listens on `127.0.0.1`. Every action needs a per-session token, so other websites cannot launch anything on your machine.

## License

[MIT](LICENSE). The bundled fonts keep their own license (below).

## Credits

[Host Grotesk](https://github.com/Element-Type/HostGrotesk) and [Instrument Sans](https://github.com/Instrument/instrument-sans) fonts, under the SIL Open Font License (see `ludotek/web/fonts/`).
