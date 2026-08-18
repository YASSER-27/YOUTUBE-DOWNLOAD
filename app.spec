# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_data_files

# Check if dist/engine.exe exists, and bundle it in datas
extra_datas = [
    ('icon.ico', '.'),
]
if os.path.exists('dist/engine.exe'):
    extra_datas.append(('dist/engine.exe', '.'))
elif os.path.exists('engine.exe'):
    extra_datas.append(('engine.exe', '.'))

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=collect_data_files('PySide6.QtGui', includes=['imageformats/**']) + extra_datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PySide6.QtWebEngineWidgets', 'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineQuick', 'PySide6.QtQml', 'PySide6.QtQuick',
        'PySide6.QtQuickWidgets', 'PySide6.QtWebChannel',
        'PySide6.QtCharts', 'PySide6.QtPdf', 'PySide6.QtPdfWidgets',
        'PySide6.QtSvg', 'PySide6.QtSql', 'PySide6.QtTest', 'PySide6.QtXml',
        'PySide6.Qt3DCore', 'PySide6.Qt3DRender', 'PySide6.Qt3DExtras',
        'PySide6.QtNetworkAuth', 'PySide6.QtSensors', 'PySide6.QtBluetooth',
        'PySide6.QtPositioning', 'PySide6.QtLocation', 'PySide6.QtDesigner',
        'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets',
        'webview', 'clr_loader',
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

# Drop Qt DLLs we never use
_DROP = {
    'opengl32sw.dll', 'Qt6Quick.dll', 'Qt6Qml.dll', 'Qt6QmlMeta.dll',
    'Qt6QmlModels.dll', 'Qt6QmlWorkerScript.dll', 'Qt6QmlCompiler.dll',
    'Qt6Pdf.dll', 'Qt6PdfWidgets.dll', 'Qt6Svg.dll', 'Qt6VirtualKeyboard.dll',
    'Qt6Positioning.dll', 'Qt6WebChannel.dll', 'Qt6PrintSupport.dll',
    'pyside6qml.abi3.dll', 'Qt6MultimediaQuick.dll', 'Qt6Multimedia.dll',
    'Qt6MultimediaWidgets.dll', 'Qt6Network.dll', 'Qt6OpenGL.dll',
    'Qt6OpenGLWidgets.dll', 'Qt6SvgWidgets.dll', 'Qt6QuickWidgets.dll',
    'Qt6DBus.dll',
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