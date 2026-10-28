# Giperion/packaging/giperion.spec                                     v001
# PyInstaller one-dir сборка GUI Giperion.
# Запуск: python -m tools.build_release

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).resolve().parent

datas = [
    (str(ROOT / "skins"), "skins"),
    (str(ROOT / "knowledge"), "knowledge"),
    (str(ROOT / "docs"), "docs"),
    (str(ROOT / "assets"), "assets"),
    (str(ROOT / "main_window.ui"), "."),
]

for package in ("giperion_model", "terminal", "shared"):
    datas += collect_data_files(package)

hiddenimports = []

for package in ("giperion_model", "terminal", "shared", "tools"):
    hiddenimports += collect_submodules(package)

a = Analysis(
    [str(ROOT / "gui.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["pytest", "ruff", "tests"],
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
