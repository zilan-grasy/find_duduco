# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['find_duduco.py'],
    pathex=[],
    binaries=[],
    datas=[('userdata', 'userdata')],
    hiddenimports=['cv2', 'numpy', 'PIL', 'PIL.Image', 'PIL.ImageGrab', 'PIL.ImageTk',
                   'duduco_solve', 'grid_recog', 'ctypes', 'json', 'tkinter', 'tkinter.ttk'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='寻找嘟嘟可',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
