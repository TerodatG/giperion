# Giperion/packaging/giperion.spec                                     v002
# PyInstaller one-dir СЃР±РѕСЂРєР° GUI Giperion.
# Р—Р°РїСѓСЃРє: python -m tools.build_release
#
# РњРѕРґРµР»СЊ РІС‹РЅРµСЃРµРЅР° РІ РѕС‚РґРµР»СЊРЅС‹Р№ РїСЂРѕРµРєС‚ Kraper Рё СЃС‚Р°РІРёС‚СЃСЏ РєР°Рє РїР°РєРµС‚
# kraper_model (pip install -e ../Kraper).

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).resolve().parent

# Kraper СЃС‚Р°РІРёС‚СЃСЏ РєР°Рє РїР°РєРµС‚ kraper_model. Editable-СѓСЃС‚Р°РЅРѕРІРєСѓ PyInstaller
# РЅРµ РІРёРґРёС‚, РїРѕСЌС‚РѕРјСѓ РґРѕР±Р°РІР»СЏРµРј РёСЃС…РѕРґРЅРёРєРё СЃРѕСЃРµРґРЅРµРіРѕ РїСЂРѕРµРєС‚Р° РІ sys.path.
KRAPER = Path(os.environ.get("KRAPER_PATH", ROOT.parent / "Kraper"))

if KRAPER.is_dir() and str(KRAPER) not in sys.path:
    sys.path.insert(0, str(KRAPER))

pathex = [str(ROOT)] + ([str(KRAPER)] if KRAPER.is_dir() else [])

datas = [
    (str(ROOT / "skins"), "skins"),
    (str(ROOT / "knowledge"), "knowledge"),
    (str(ROOT / "docs"), "docs"),
    (str(ROOT / "assets"), "assets"),
    (str(ROOT / "main_window.ui"), "."),
    # РЎС‚Р°СЂС‚РѕРІС‹Р№ РєР°С‚Р°Р»РѕРі РёРЅС‚РµРЅС‚РѕРІ: Р±РµР· РЅРµРіРѕ Р°СЃСЃРёСЃС‚РµРЅС‚ РЅРµ РѕС‚РІРµС‡Р°РµС‚.
    (str(ROOT / "data" / "intents.json"), "data"),
    (str(ROOT / "models"), "models"),
]

for package in ("kraper_model", "terminal", "shared"):
    datas += collect_data_files(package)

hiddenimports = []

for package in ("kraper_model", "terminal", "shared"):
    hiddenimports += collect_submodules(package)

# Импортируется как `from tools import knowledge_add` — PyInstaller
# такой подмодуль сам не находит.
hiddenimports += ["tools.knowledge_add"]

a = Analysis(
    [str(ROOT / "gui.py")],
    pathex=pathex,
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "pytest",
        "ruff",
        "tests",
        "sklearn",
        "scipy",
        "pandas",
        "matplotlib",
        "tkinter",
        "IPython",
        "notebook",
        "jupyter",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Giperion",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Giperion",
)

# РќР° macOS СЃРѕР±РёСЂР°РµРј РЅР°СЃС‚РѕСЏС‰РёР№ .app: РµРіРѕ Р¶РґС‘С‚ packaging/macos/build_dmg.sh.
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Giperion.app",
        bundle_identifier="com.giperion.app",
        info_plist={
            "NSHighResolutionCapable": True,
            "CFBundleShortVersionString": "1.0.0",
        },
    )


