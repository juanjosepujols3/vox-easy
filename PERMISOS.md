# 🔐 Guía de Permisos Persistentes - Vox Easy

## 🚨 Problema

Cada vez que actualizas la app, macOS te pide permisos de nuevo (Micrófono + Accesibilidad).

**¿Por qué pasa?**
- macOS identifica apps por su **firma digital** (code signature)
- Ad-hoc signing (`--sign -`) genera una firma diferente cada build
- macOS piensa que es una "app nueva" → resetea permisos

## ✅ Solución: Certificate Consistente

### Paso 1: Crear Certificate (Solo UNA vez)

```bash
./create_signing_certificate.sh
```

Esto crea un certificate self-signed llamado **"Vox Easy Developer"** que se mantiene igual entre builds.

### Paso 2: Compilar con el Certificate

```bash
./build.sh
```

El script detecta automáticamente si existe el certificate y lo usa. Verás:

```
✅ Usando certificate: Vox Easy Developer (permisos persistentes)
```

Si ves esto en cambio:
```
⚠️  Usando ad-hoc signing (permisos se resetearán)
```

→ Ejecuta el Paso 1 primero.

### Paso 3: Instalar Correctamente

**SIEMPRE instala en /Applications:**

```bash
./install.sh "dist-intel/Vox Easy.app"
```

El instalador:
- ✅ Cierra la versión anterior si está corriendo
- ✅ Remueve la app vieja
- ✅ Instala la nueva EN EL MISMO LUGAR
- ✅ Remueve quarantine flag
- ✅ Los permisos se mantienen 🎉

### Paso 4: Dar Permisos (Solo la PRIMERA vez)

La primera vez que uses la app:

1. **Micrófono**
   - Sistema → Privacidad y Seguridad → Micrófono
   - → ✓ Vox Easy

2. **Accesibilidad**
   - Sistema → Privacidad y Seguridad → Accesibilidad
   - → ✓ Vox Easy

**Actualizaciones futuras:** Los permisos se mantienen automáticamente 🎉

---

## 🔄 Flujo Completo

```bash
# 1. Primera vez: Crear certificate (SOLO UNA VEZ)
./create_signing_certificate.sh

# 2. Compilar (cada actualización)
./build.sh

# 3. Instalar (cada actualización)
./install.sh "dist-intel/Vox Easy.app"

# 4. Dar permisos en System Preferences (SOLO PRIMERA VEZ)
```

---

## 🎯 Verificar que Funciona

Después de instalar una actualización:

```bash
# Verificar bundle identifier (debe ser siempre el mismo)
defaults read "/Applications/Vox Easy.app/Contents/Info.plist" CFBundleIdentifier
# Debe mostrar: com.voxeasy.app

# Verificar firma
codesign -dv "/Applications/Vox Easy.app" 2>&1 | grep Authority
# Debe mostrar: Authority=Vox Easy Developer
```

Si el Authority es siempre el mismo → ✅ Permisos persistirán

---

## ⚠️ Importante

### ✅ Hacer:
- Usar `./create_signing_certificate.sh` **una sola vez**
- Compilar con `./build.sh`
- Instalar con `./install.sh` **siempre en /Applications**
- Mantener el bundle ID: `com.voxeasy.app`

### ❌ NO Hacer:
- Cambiar el bundle identifier
- Usar `--sign -` manualmente
- Instalar en ubicaciones diferentes
- Borrar el certificate del Keychain

---

## 🐛 Troubleshooting

### Los permisos aún se resetean

1. Verificar que el certificate existe:
```bash
security find-identity -v -p codesigning | grep "Vox Easy"
```

2. Verificar que la app está firmada correctamente:
```bash
codesign -dv "/Applications/Vox Easy.app"
```

3. Verificar que el bundle ID es consistente:
```bash
defaults read "/Applications/Vox Easy.app/Contents/Info.plist" CFBundleIdentifier
```

### Resetear permisos manualmente

Si necesitas empezar de cero:

```bash
# Remover permisos de Vox Easy
tccutil reset Microphone com.voxeasy.app
tccutil reset Accessibility com.voxeasy.app

# Desinstalar app
rm -rf "/Applications/Vox Easy.app"

# Volver a instalar
./install.sh "dist-intel/Vox Easy.app"
```

---

## 📚 Más Información

- Bundle Identifier: `com.voxeasy.app`
- Certificate: `Vox Easy Developer` (self-signed, local)
- Entitlements: `entitlements.plist`
- Permisos: Micrófono (`com.apple.security.device.audio-input`) + Accesibilidad (`com.apple.security.automation.apple-events`)
