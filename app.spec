# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

extra_datas = [
    ('icon.ico', '.'),
]
if os.path.exists('dist/engine.exe'):
    extra_datas.append(('dist/engine.exe', '.'))
if os.path.exists('engine.exe') and ('engine.exe', '.') not in extra_datas:
    extra_datas.append(('engine.exe', '.'))

a = Analysis(
    ['app.py'],
    pathex=['.'],
    binaries=[],
    datas=collect_data_files('yt_dlp') + extra_datas,
    hiddenimports=collect_submodules('yt_dlp') + [
        'PyQt5', 'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets', 'PyQt5.QtSvg',
        'static_ffmpeg', 'cffi', '_cffi_backend', 'urllib.request', 'json', 'ssl', 'websockets'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PySide6', 'PySide2', 'PyQt6',
        'PyQt5.QtWebEngineWidgets', 'PyQt5.QtWebEngineCore', 'PyQt5.QtWebEngine',
        'PyQt5.QtQml', 'PyQt5.QtQuick', 'PyQt5.QtQuickWidgets',
        'PyQt5.QtNetworkAuth', 'PyQt5.QtSensors', 'PyQt5.QtBluetooth',
        'PyQt5.QtPositioning', 'PyQt5.QtLocation', 'PyQt5.QtDesigner',
        'PyQt5.QtMultimedia', 'PyQt5.QtMultimediaWidgets',
        'PyQt5.QtSql', 'PyQt5.QtTest', 'PyQt5.QtXml',
        'webview', 'clr_loader', 'torch', 'transformers', 'scipy', 'matplotlib'
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

# Drop heavy Qt5 DLLs not used by our app
_DROP = {
    'opengl32sw.dll', 'Qt5Quick.dll', 'Qt5Qml.dll', 'Qt5QmlModels.dll',
    'Qt5QmlWorkerScript.dll', 'Qt5Pdf.dll', 'Qt5PdfWidgets.dll',
    'Qt5VirtualKeyboard.dll', 'Qt5Positioning.dll', 'Qt5WebChannel.dll',
    'Qt5MultimediaQuick.dll', 'Qt5Multimedia.dll', 'Qt5MultimediaWidgets.dll',
    'Qt5OpenGL.dll', 'Qt5OpenGLWidgets.dll', 'Qt5QuickWidgets.dll', 'Qt5DBus.dll',
    'Qt5Sensors.dll', 'Qt5Location.dll', 'Qt5Bluetooth.dll', 'Qt5Nfc.dll',
}
a.binaries = [b for b in a.binaries if os.path.basename(b[0]) not in _DROP]
a.datas = [d for d in a.datas if os.path.basename(d[0]) not in _DROP]

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Download Free',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico'
)