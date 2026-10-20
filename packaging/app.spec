# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Windows build.

Run from the repository root:
    python -m PyInstaller packaging/app.spec --noconfirm
"""

import os
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

# A conda Python keeps some runtime DLLs in Library\bin instead of next to
# python.exe.  PyInstaller's dependency scanner does not look there, so add
# the ones used by _ctypes / _ssl / compression modules explicitly.
binaries = []
conda_bin = os.path.join(sys.prefix, "Library", "bin")
for dll_name in (
    "ffi.dll",
    "libcrypto-3-x64.dll",
    "libssl-3-x64.dll",
    "liblzma.dll",
    "LIBBZ2.dll",
    "libexpat.dll",
    "zlib.dll",
):
    dll_path = os.path.join(conda_bin, dll_name)
    if os.path.exists(dll_path):
        binaries.append((dll_path, "."))


hiddenimports = [
    "PIL.Image",
    "PIL.ImageGrab",
    "winrt.windows.foundation",
    "winrt.windows.foundation.collections",
    "winrt.windows.globalization",
    "winrt.windows.graphics.imaging",
    "winrt.windows.media.ocr",
    "winrt.windows.storage.streams",
]
try:
    hiddenimports += collect_submodules("winrt")
except Exception:
    pass

datas = [
    (os.path.join(ROOT, "assets", "icon.png"), "assets"),
    (os.path.join(ROOT, "assets", "tray-icon.ico"), "assets"),
    (os.path.join(ROOT, "assets", "tray-icon.png"), "assets"),
    (os.path.join(ROOT, "assets", "buyMeCoffee", "wechat.jpg"), "assets/buyMeCoffee"),
    (os.path.join(ROOT, "assets", "buyMeCoffee", "alipay.jpg"), "assets/buyMeCoffee"),
]
try:
    datas += collect_data_files("winrt")
except Exception:
    pass

a = Analysis(
    [os.path.join(ROOT, "run_app.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "scipy", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MagicallyEncircle",
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
    icon=os.path.join(ROOT, "assets", "app.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="MagicallyEncircle",
)
