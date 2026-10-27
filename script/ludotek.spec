# -*- mode: python ; coding: utf-8 -*-
# Single source of the build settings. Run: pyinstaller --clean --noconfirm script/ludotek.spec
# (or script/build.ps1 / script/build.sh). Build on Windows to get a Windows .exe: PyInstaller does not cross-compile.
import os

ROOT = os.path.dirname(SPECPATH)  # this spec lives in script/

a = Analysis(
    [os.path.join(ROOT, "ludotek", "__main__.py")],
    pathex=[ROOT],  # so the entry script's "from ludotek import ..." resolves
    # Without the UI files the exe starts but serves no page.
    datas=[(os.path.join(ROOT, "ludotek", "web"), "ludotek/web")],
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Ludotek",
    upx=True,
    # Visible console on purpose: closing it stops the server, so nothing keeps running
    # in the background after the browser tab is closed.
    console=True,
)
