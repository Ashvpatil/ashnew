# PyInstaller spec for TWGBG
block_cipher = None

a = Analysis(
    ['twgbg/gui/app.py'],
    pathex=['.'],
    binaries=[],
    datas=[('twgbg/data', 'twgbg/data'), ('twgbg/puzzles', 'twgbg/puzzles'), ('twgbg/docs', 'twgbg/docs')],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='twgbg',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='twgbg'
)
