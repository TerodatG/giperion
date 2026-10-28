# Giperion/packaging/giperion.spec                                     v001
# PyInstaller one-dir сборка GUI Giperion.
# Запуск: python -m tools.build_release

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).resolve().parent

# Пакет giperion_model лежит в model/, а не в корне: без этого он
# не попадает в сборку и приложение падает с ModuleNotFoundError.
MODEL = ROOT / "model"

if str(MODEL) not in sys.path:
    sys.path.insert(0, str(MODEL))

datas = [
    (str(ROOT / "skins"), "skins"),
    (str(ROOT / "knowledge"), "knowledge"),
    (str(ROOT / "docs"), "docs"),
    (str(ROOT / "assets"), "assets"),
    (str(ROOT / "main_window.ui"), "."),
    # Веса модели и стартовый каталог интентов: без них GUI запускается,
    # но не отвечает на сообщения.
    (str(ROOT / "models"), "models"),
    (str(ROOT / "data" / "intents.json"), "data"),
]

for package in ("giperion_model", "terminal", "shared"):
    datas += collect_data_files(package)

hiddenimports = []

for package in ("giperion_model", "terminal", "shared"):
    hiddenimports += collect_submodules(package)

a = Analysis(
    [str(ROOT / "gui.py")],
    pathex=[str(ROOT), str(MODEL)],
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

# На macOS собираем настоящий .app: его ждёт packaging/macos/build_dmg.sh.
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
