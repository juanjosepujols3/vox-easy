#!/bin/bash
# Script para crear un certificate self-signed para firmar Vox Easy
# Este certificate es consistente entre builds, manteniendo los permisos

CERT_NAME="Vox Easy Developer"
KEYCHAIN="login.keychain-db"

echo "🔐 Verificando certificate de firma..."

# Verificar si ya existe el certificate
if security find-identity -v -p codesigning | grep -q "$CERT_NAME"; then
    echo "✅ Certificate '$CERT_NAME' ya existe"
    echo ""
    echo "Para firmar la app usa:"
    echo "  codesign --deep --force --sign \"$CERT_NAME\" \\"
    echo "      --entitlements entitlements.plist \\"
    echo "      --options runtime \\"
    echo "      \"dist-intel/Vox Easy.app\""
    exit 0
fi

echo "📝 Creando certificate self-signed..."
echo "   Esto solo se hace UNA VEZ"
echo ""

# Crear certificate self-signed
cat > /tmp/cert-config.txt << EOF
[ req ]
default_bits = 2048
distinguished_name = req_distinguished_name
x509_extensions = v3_req

[ req_distinguished_name ]
commonName = Vox Easy Developer

[ v3_req ]
basicConstraints = CA:FALSE
keyUsage = digitalSignature
extendedKeyUsage = codeSigning
EOF

# Generar certificate
openssl req -new -newkey rsa:2048 -nodes -x509 -days 3650 \
    -keyout /tmp/cert.key \
    -out /tmp/cert.crt \
    -subj "/CN=Vox Easy Developer/O=Vox Easy/C=US" \
    -config /tmp/cert-config.txt

# Crear p12
openssl pkcs12 -export -out /tmp/cert.p12 \
    -inkey /tmp/cert.key \
    -in /tmp/cert.crt \
    -password pass:voxeasy

# Importar a keychain
security import /tmp/cert.p12 -k ~/Library/Keychains/$KEYCHAIN -P voxeasy -T /usr/bin/codesign

# Dar trust
security add-trusted-cert -d -r trustRoot -k ~/Library/Keychains/$KEYCHAIN /tmp/cert.crt

# Permitir que codesign use el certificate sin pedir password
security set-key-partition-list -S apple-tool:,apple: -s -k "" ~/Library/Keychains/$KEYCHAIN

# Cleanup
rm -f /tmp/cert.key /tmp/cert.crt /tmp/cert.p12 /tmp/cert-config.txt

echo ""
echo "✅ Certificate creado exitosamente!"
echo ""
echo "🔑 Certificate: $CERT_NAME"
echo ""
echo "Para firmar la app usa:"
echo "  codesign --deep --force --sign \"$CERT_NAME\" \\"
echo "      --entitlements entitlements.plist \\"
echo "      --options runtime \\"
echo "      \"dist-intel/Vox Easy.app\""
echo ""
echo "⚠️  IMPORTANTE: Este certificate solo funciona en tu Mac."
echo "    NO intentes distribuir la app firmada con este certificate."
echo "    Para distribución pública necesitas Apple Developer account."
