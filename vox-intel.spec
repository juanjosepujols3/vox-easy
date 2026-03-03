# -*- mode: python ; coding: utf-8 -*-
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('web/', 'web/'),
        ('assets/', 'assets/'),
    ],
    hiddenimports=[
        'webview', 'requests', 'sounddevice',
        'scipy.io.wavfile', 'scipy.io', 'scipy',
        'numpy', 'httpx', 'httpx._transports.default',
        'engine.audio', 'engine.keyboard', 'engine.storage',
        'engine.transcriber', 'engine.text_processing',
        'engine.file_indexer', 'engine.dev_terms',
        'pyautogui', 'ApplicationServices', 'AppKit', 'Cocoa',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=['faster_whisper', 'ctranslate2', 'onnxruntime', 'torch',
              'whisper', 'customtkinter', 'pynput', 'tkinter', 'PyQt5',
              'uvloop'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='Vox Easy Intel',
    debug=False,
    strip=False,
    upx=False,
    console=False,
    target_arch='x86_64',
)
coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False, upx=False,
    name='Vox Easy Intel',
)
app = BUNDLE(
    coll,
    name='Vox Easy.app',
    icon='assets/VoxEasy.icns',
    bundle_identifier='com.voxeasy.app',
    info_plist={
        'CFBundleName': 'Vox Easy',
        'CFBundleDisplayName': 'Vox Easy',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSMicrophoneUsageDescription': 'Vox Easy necesita acceso al micrófono para transcribir tu voz.',
        'NSAppleEventsUsageDescription': 'Vox Easy necesita permisos de accesibilidad para escribir texto automáticamente.',
        'LSMinimumSystemVersion': '12.0',
    },
)
