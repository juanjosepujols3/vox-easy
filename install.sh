#!/bin/bash
# Instalador inteligente de Vox Easy
# Preserva permisos de macOS entre actualizaciones

set -e

APP_NAME="Vox Easy.app"
BUNDLE_ID="com.voxeasy.app"
INSTALL_PATH="/Applications/$APP_NAME"
SOURCE_APP="$1"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  📦 Instalador de Vox Easy"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Verificar que se pasó la ruta a la app
if [ -z "$SOURCE_APP" ]; then
    echo -e "${RED}❌ Error: Debes especificar la ruta a la app${NC}"
    echo ""
    echo "Uso:"
    echo "  ./install.sh \"dist-intel/Vox Easy.app\""
    echo "  ./install.sh \"dist/Vox Easy.app\""
    exit 1
fi

# Verificar que la app existe
if [ ! -d "$SOURCE_APP" ]; then
    echo -e "${RED}❌ Error: No se encuentra la app en: $SOURCE_APP${NC}"
    exit 1
fi

# Verificar bundle identifier
SOURCE_BUNDLE_ID=$(defaults read "$SOURCE_APP/Contents/Info.plist" CFBundleIdentifier 2>/dev/null || echo "")
if [ "$SOURCE_BUNDLE_ID" != "$BUNDLE_ID" ]; then
    echo -e "${YELLOW}⚠️  Warning: Bundle ID no coincide${NC}"
    echo "   Esperado: $BUNDLE_ID"
    echo "   Encontrado: $SOURCE_BUNDLE_ID"
    echo ""
fi

# Verificar si hay una versión anterior instalada
if [ -d "$INSTALL_PATH" ]; then
    echo -e "${YELLOW}📋 Versión anterior detectada${NC}"

    # Obtener versiones
    OLD_VERSION=$(defaults read "$INSTALL_PATH/Contents/Info.plist" CFBundleShortVersionString 2>/dev/null || echo "unknown")
    NEW_VERSION=$(defaults read "$SOURCE_APP/Contents/Info.plist" CFBundleShortVersionString 2>/dev/null || echo "unknown")

    echo "   Versión instalada: $OLD_VERSION"
    echo "   Nueva versión: $NEW_VERSION"
    echo ""

    # Verificar si la app está corriendo
    if pgrep -f "$INSTALL_PATH" > /dev/null; then
        echo -e "${YELLOW}⚠️  Vox Easy está corriendo, cerrando...${NC}"
        killall "Vox Easy" 2>/dev/null || true
        sleep 2
    fi

    echo "🗑️  Removiendo versión anterior..."
    rm -rf "$INSTALL_PATH"
    echo ""
fi

# Copiar nueva versión
echo "📦 Instalando Vox Easy en /Applications..."
cp -R "$SOURCE_APP" "$INSTALL_PATH"

# Remover quarantine flag (evita warning de "desarrollador no identificado")
echo "🔓 Removiendo quarantine flag..."
xattr -cr "$INSTALL_PATH"

# Verificar permisos en System Preferences
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✅ Instalación completada${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📍 Ubicación: $INSTALL_PATH"
echo ""
echo "🔐 PERMISOS REQUERIDOS:"
echo ""
echo "   1️⃣  Micrófono"
echo "       Sistema → Privacidad y Seguridad → Micrófono"
echo "       → ✓ Vox Easy"
echo ""
echo "   2️⃣  Accesibilidad"
echo "       Sistema → Privacidad y Seguridad → Accesibilidad"
echo "       → ✓ Vox Easy"
echo ""
echo "⚠️  IMPORTANTE:"
echo "   - Si actualizaste la app, los permisos deberían mantenerse"
echo "   - Si es instalación nueva, la app pedirá permisos al usarla"
echo "   - El bundle ID ($BUNDLE_ID) mantiene los permisos entre actualizaciones"
echo ""
echo "🚀 Para abrir la app:"
echo "   open \"$INSTALL_PATH\""
echo ""
