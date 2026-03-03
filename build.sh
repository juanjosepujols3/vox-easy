#!/bin/bash
set -e
echo "=== Vox Easy Build Script ==="

VERSION="1.0.8"
RELEASE_DIR="$HOME/Desktop/DMG - Vox Easy"
mkdir -p "$RELEASE_DIR"

ARCH=$(uname -m)
echo "Host architecture: $ARCH"

# ---- Función para crear el DMG estilo nativo Apple ----
make_dmg() {
    local APP_PATH="$1"     # path al .app compilado
    local ARCH_LABEL="$2"   # "Intel" o "arm64"
    local OUT="$RELEASE_DIR/VoxEasy-$ARCH_LABEL-$VERSION.dmg"

    echo "  Creando DMG $ARCH_LABEL..."
    # Eliminar DMG anterior si existe (create-dmg no sobreescribe)
    rm -f "$OUT"

    create-dmg \
        --volname "Vox Easy" \
        --volicon "assets/VoxEasy.icns" \
        --background "assets/dmg_background.png" \
        --window-pos 200 120 \
        --window-size 660 420 \
        --icon-size 110 \
        --icon "Vox Easy.app" 165 210 \
        --hide-extension "Vox Easy.app" \
        --app-drop-link 495 210 \
        --no-internet-enable \
        "$OUT" \
        "$APP_PATH"

    echo "✓ VoxEasy-$ARCH_LABEL-$VERSION.dmg"
}

# ---- Apple Silicon build (arm64) ----
if [ "$ARCH" = "arm64" ]; then
    echo "[1/2] Building arm64 (Apple Silicon)..."
    .venv/bin/pyinstaller vox-arm64.spec --clean --noconfirm
    codesign --deep --force --sign - "dist/Vox Easy.app"
    make_dmg "dist/Vox Easy.app" "arm64"
else
    echo "[SKIP] arm64 build requiere Mac con Apple Silicon (M1/M2/M3/M4)."
    echo "       Copia vox-arm64.spec a una Mac Silicon, crea un venv nativo y corre:"
    echo "       .venv/bin/pyinstaller vox-arm64.spec --clean --noconfirm"
fi

# ---- Intel build (x86_64) ----
echo "[2/2] Building Intel (x86_64)..."
if [ "$ARCH" = "arm64" ]; then
    if [ ! -d ".venv-intel" ]; then
        echo "ERROR: Falta .venv-intel. Ejecuta primero:"
        echo "  arch -x86_64 ~/.pyenv/versions/3.9.6/bin/python3 -m venv .venv-intel"
        echo "  arch -x86_64 .venv-intel/bin/pip install -r requirements-app.txt pyinstaller"
        exit 1
    fi
    arch -x86_64 .venv-intel/bin/pyinstaller vox-intel.spec --clean --noconfirm \
      --distpath dist-intel
    DIST_INTEL="dist-intel"
else
    .venv/bin/pyinstaller vox-intel.spec --clean --noconfirm --distpath dist-intel
    DIST_INTEL="dist-intel"
fi

codesign --deep --force --sign - "$DIST_INTEL/Vox Easy.app"
make_dmg "$DIST_INTEL/Vox Easy.app" "Intel"

echo ""
echo "=== Done ==="
ls -lh "$RELEASE_DIR/"
