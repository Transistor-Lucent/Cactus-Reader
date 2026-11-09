# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build recipe for the portable Cactus Reader folder build."""

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

# The icon, logo and any future visual assets travel with the executable.
datas = [("assets", "assets")]

# PyMuPDF ships its native bindings beside the Python package.  Collecting the
# dynamic libraries explicitly keeps the MuPDF fallback working in the frozen
# application even on machines without a Python installation.
datas += collect_data_files(
    "pymupdf",
    excludes=["**/mupdf-devel/**", "**/__pycache__/**", "**/*.py"],
)
binaries = collect_dynamic_libs("pymupdf")
hiddenimports = [
    "pymupdf",
    "pymupdf.extra",
    "pymupdf._extra",
    "pymupdf.mupdf",
    "pymupdf._mupdf",
    "pymupdf.utils",
    "pymupdf.table",
]

a = Analysis(
    ["main.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # This is a Qt Widgets application; keep unused Qt modules out of the
        # portable folder.
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebEngineQuick",
        "PySide6.QtQuick",
        "PySide6.QtQml",
        "PySide6.Qt3DCore",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.QtPdf",
        "PySide6.QtPdfWidgets",
        "PySide6.QtSql",
        "PySide6.QtTest",
        "tkinter",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CactusReader",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/icon.ico",
    version="version_info.txt",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="CactusReader",
)
