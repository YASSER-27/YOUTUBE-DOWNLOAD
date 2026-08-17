# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = []
hiddenimports += collect_submodules('PySide6.QtMultimedia')
hiddenimports += collect_submodules('PySide6.QtMultimediaWidgets')

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=collect_data_files('PySide6.QtGui', includes=['imageformats/**']) +
          collect_data_files('PySide6.QtMultimedia', includes=['plugins/**']) +
          collect_data_files('PySide6.QtMultimediaWidgets') +
          [
              ('icon.ico', '.'),
          ],
    hiddenimports=hiddenimports,
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
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)


# Drop Qt DLLs we never use (they are pulled in by the generic PySide6 hook).
_DROP = {
    'opengl32sw.dll', 'Qt6Quick.dll', 'Qt6Qml.dll', 'Qt6QmlMeta.dll',
    'Qt6QmlModels.dll', 'Qt6QmlWorkerScript.dll', 'Qt6QmlCompiler.dll',
    'Qt6Pdf.dll', 'Qt6PdfWidgets.dll', 'Qt6Svg.dll', 'Qt6VirtualKeyboard.dll',
    'Qt6Positioning.dll', 'Qt6WebChannel.dll', 'Qt6PrintSupport.dll',
    'pyside6qml.abi3.dll', 'Qt6MultimediaQuick.dll',
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
    icon=['icon.ico'],
)