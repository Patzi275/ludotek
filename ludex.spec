# -*- mode: python ; coding: utf-8 -*-
# Single source of the build settings. Run: pyinstaller --clean --noconfirm ludex.spec
# (or build.ps1 / build.sh). Build on Windows to get a Windows .exe: PyInstaller does not cross-compile.
import os

a = Analysis(
    [os.path.join(SPECPATH, "library.py")],
    # Without the UI files the exe starts but serves no page.
    datas=[(os.path.join(SPECPATH, "gamelib", "web"), "gamelib/web")],
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Ludex",
    upx=True,
    # Visible console on purpose: closing it stops the server, so nothing keeps running
    # in the background after the browser tab is closed.
    console=True,
)
