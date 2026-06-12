# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['japp.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('index.html', '.'),
        ('style.css', '.'),
        ('script.js', '.')
    ],
    hiddenimports=[],
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
    exclude_binaries=True,
    name='JApp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='JApp',
)

# Custom post-build step to copy Favorites.json next to JApp.exe (as required by get_data_path)
import shutil
import os
try:
    dest_fav = os.path.join('dist', 'JApp', 'Favorites.json')
    if os.path.exists(dest_fav):
        print(">>> spec post-build: Favorites.json already exists in dist/JApp/. Skipping copy to avoid overwriting user database.")
    else:
        # Search candidate source paths
        src_candidates = [
            'Favorites.json',
            os.path.join('dist', 'JApp', 'Favorites.json.tmp'),
            'Favorites.json.tmp',
            'Favorites.json.corrupted.bak'
        ]
        copied = False
        for src in src_candidates:
            if os.path.exists(src):
                os.makedirs(os.path.dirname(dest_fav), exist_ok=True)
                shutil.copy2(src, dest_fav)
                print(f">>> spec post-build: Copied {src} to {dest_fav} successfully!")
                copied = True
                break
        if not copied:
            print(">>> spec post-build WARNING: No source Favorites.json found to copy.")
except Exception as e:
    print(">>> spec post-build ERROR: Failed to copy Favorites.json:", e)
