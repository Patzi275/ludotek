#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SPEC_FILE="$PROJECT_ROOT/ludex.spec"
WEB_DIRECTORY="$PROJECT_ROOT/gamelib/web"
DIST_DIRECTORY="$PROJECT_ROOT/dist"
EXECUTABLE="$DIST_DIRECTORY/Ludex.exe"

if [[ ! -f "$SPEC_FILE" ]]; then
    echo "Fichier de build introuvable : $SPEC_FILE" >&2
    exit 1
fi

for file in index.html app.js style.css; do
    if [[ ! -f "$WEB_DIRECTORY/$file" ]]; then
        echo "Ressource web introuvable : $WEB_DIRECTORY/$file" >&2
        exit 1
    fi
done

PYTHON="${PYTHON:-}"
if [[ -z "$PYTHON" ]]; then
    if command -v python3 >/dev/null 2>&1; then
        PYTHON="$(command -v python3)"
    elif command -v python >/dev/null 2>&1; then
        PYTHON="$(command -v python)"
    elif command -v py.exe >/dev/null 2>&1; then
        PYTHON="$(command -v py.exe)"
    else
        echo "Python est introuvable. Installez Python 3.8 ou une version plus récente." >&2
        exit 1
    fi
fi

if ! "$PYTHON" -m PyInstaller --version >/dev/null 2>&1; then
    echo "PyInstaller est introuvable. Installez-le avec : $PYTHON -m pip install pyinstaller" >&2
    exit 1
fi

case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*)
        EXECUTABLE="$DIST_DIRECTORY/Ludex.exe"
        ;;
    *)
        # PyInstaller builds for the current OS: on Linux/WSL this is a Linux binary, not the Windows .exe.
        echo "Attention : ce build produit un exécutable Linux. Pour le .exe Windows, lance build.ps1 sous Windows." >&2
        EXECUTABLE="$DIST_DIRECTORY/Ludex"
        ;;
esac

echo "Construction de Ludex avec PyInstaller $("$PYTHON" -m PyInstaller --version)..."

cd "$PROJECT_ROOT"
"$PYTHON" -m PyInstaller \
    --clean \
    --noconfirm \
    --distpath "$DIST_DIRECTORY" \
    --workpath "$PROJECT_ROOT/build" \
    "$SPEC_FILE"

if [[ ! -f "$EXECUTABLE" ]]; then
    echo "L'exécutable attendu n'a pas été créé : $EXECUTABLE" >&2
    exit 1
fi

size_bytes="$(wc -c < "$EXECUTABLE")"
size_mb="$(awk -v bytes="$size_bytes" 'BEGIN { printf "%.2f", bytes / 1048576 }')"
echo "Construction terminée : $EXECUTABLE ($size_mb Mo)"

