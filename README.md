# Ludex

A portable game library for a folder of PC games. Drop `Ludex.exe` next to your games and it turns the folder into a browsable library. Nothing to install, it works offline, and it never writes to your user profile.

The interface is in French.

## Features

- Scans the folder and tells installed games, archives to extract and installers apart.
- Cleans release names (`Hollow-Knight-SteamRIP.com` → *Hollow Knight*) and flags likely duplicates.
- Finds the right executable in each game folder, skipping uninstallers, redistributables and crash handlers.
- Launches games and opens their location.
- Favorites, status, notes, description and cover art (file, URL, drag and drop or paste).
- Watches for added and removed items, and lets you switch to another games folder from the settings.

## Usage

1. Download `Ludex.exe` from the latest successful [build workflow](../../actions/workflows/build-exe.yml) run (Artifacts section).
2. Put it in your games folder and run it, or choose another folder later in **Réglages**.
3. The library opens in your browser. Close the console window (or click **Quitter**) to stop it.

Library data is stored in the games folder itself (`.bibliotheque.json`, `.bibliotheque/`). The chosen folder is remembered in `.ludex.json`, next to the exe.

## From source

Requires Python 3.8+, standard library only.

```bash
python3 library.py "D:\Jeux"         # or no argument: saved folder, else the script's folder
python3 library.py --no-browser
```

Build the exe on Windows: `pip install pyinstaller`, then `.\build.ps1` (output: `dist\Ludex.exe`). Every push to `main` also builds it in CI.

## Security

The server only listens on `127.0.0.1`. Every action needs a per-session token, so other websites cannot launch anything on your machine.

## License

[MIT](LICENSE). The bundled fonts keep their own license (below).

## Credits

[Host Grotesk](https://github.com/Element-Type/HostGrotesk) and [Instrument Sans](https://github.com/Instrument/instrument-sans) fonts, under the SIL Open Font License (see `gamelib/web/fonts/`).
