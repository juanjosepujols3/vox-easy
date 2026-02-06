# -*- mode: python ; coding: utf-8 -*-

import os
import customtkinter

ctk_path = os.path.dirname(customtkinter.__file__)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        (ctk_path, 'customtkinter/'),
    ],
    hiddenimports=[
        'pynput.keyboard._darwin',
        'pynput.mouse._darwin',
        'customtkinter',
        'requests',
        'sounddevice',
        'scipy.io.wavfile',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['faster_whisper', 'ctranslate2', 'onnxruntime', 'torch', 'whisper'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Vox Easy',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    target_arch='x86_64',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name='Vox Easy',
)

app = BUNDLE(
    coll,
    name='Vox Easy.app',
    icon=None,
    bundle_identifier='com.voxeasy.dictado',
    info_plist={
        'CFBundleName': 'Vox Easy',
        'CFBundleDisplayName': 'Vox Easy',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSMicrophoneUsageDescription': 'Vox Easy necesita acceso al microfono para transcribir tu voz.',
        'NSAppleEventsUsageDescription': 'Vox Easy necesita permisos de accesibilidad para escribir texto automaticamente.',
    },
)
