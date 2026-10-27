#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ludotek — a game library manager that lives inside the games folder.

Usage:
    1. From the repo root: python -m ludotek (or run the built Ludotek.exe).
    2. Without a folder argument it watches the saved folder, else the repo root / exe folder.
    3. The interface opens in the browser.

Options:
    python -m ludotek "D:\\Jeux"     -> watch another folder
    python -m ludotek --no-browser  -> do not open the browser

No dependencies: standard library only (Python 3.8+).
Favorites, notes, statuses and cached sizes are stored in .bibliotheque.json.
"""
import logging
import sys
import threading
import webbrowser

# Absolute imports: this file is also PyInstaller's entry script, run as a top-level module.
from ludotek import __version__, config, scanner
from ludotek.server import make_server
from ludotek.storage import save_db


def setup_logging():
    # French level names: the console is read by the end user.
    for level, name in ((logging.INFO, "INFO"), (logging.WARNING, "ATTENTION"), (logging.ERROR, "ERREUR")):
        logging.addLevelName(level, name)
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(asctime)s  %(levelname)-9s %(message)s", datefmt="%H:%M:%S")


def main():
    setup_logging()
    if not config.ROOT.is_dir():
        raise SystemExit(f"Dossier introuvable : {config.ROOT}")
    server = make_server()
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"Ludotek {__version__}")
    print(f"Dossier   : {config.ROOT}")
    print(f"Interface : {url}")
    print("Pour arrêter : ferme cette fenêtre, Ctrl+C, ou le bouton Quitter.")
    print("Fermer l'onglet du navigateur n'arrête pas l'application.")
    print()
    scanner.scan()
    threading.Thread(target=scanner.worker, daemon=True).start()
    threading.Thread(target=scanner.rescan_loop, daemon=True).start()
    if "--no-browser" not in sys.argv:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    save_db()
    logging.getLogger(__name__).info("Application arrêtée.")


if __name__ == "__main__":
    main()
