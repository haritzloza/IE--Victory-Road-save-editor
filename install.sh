#!/bin/sh
# Instala el ejecutable en ~/.local/bin y lo añade al menú de aplicaciones.
# Desinstalar: ./install.sh --uninstall
set -e
cd "$(dirname "$(readlink -f "$0")")"
BIN="$HOME/.local/bin/ievr-save-editor"
ICON="$HOME/.local/share/icons/hicolor/256x256/apps/ievr-save-editor.png"
DESKTOP="$HOME/.local/share/applications/ievr-save-editor.desktop"

if [ "$1" = "--uninstall" ]; then
    rm -f "$BIN" "$ICON" "$DESKTOP"
    echo "Desinstalado."
    exit 0
fi

[ -x dist/ievr-save-editor ] || { echo "Falta dist/ievr-save-editor: ejecuta ./build.sh primero"; exit 1; }
install -Dm755 dist/ievr-save-editor "$BIN"
install -Dm644 ievr_editor/data/icon.png "$ICON"
mkdir -p "$(dirname "$DESKTOP")"
cat > "$DESKTOP" <<EOF
[Desktop Entry]
Type=Application
Name=IEVR Save Editor
GenericName=Editor de partidas
Comment=Editor de partidas de INAZUMA ELEVEN: Victory Road
Exec=$BIN
Icon=ievr-save-editor
Terminal=false
Categories=Game;Utility;
StartupWMClass=ievr-save-editor
EOF
update-desktop-database "$(dirname "$DESKTOP")" 2>/dev/null || true
echo "Instalado: busca «IEVR Save Editor» en el menú de aplicaciones."
