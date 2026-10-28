#!/usr/bin/env bash
# Giperion/packaging/linux/build_appimage.sh                         v001
# Собирает AppImage из one-dir сборки PyInstaller (нужен appimagetool).
# Usage: bash packaging/linux/build_appimage.sh 1.0.0 dist/Giperion dist

set -euo pipefail

VERSION="${1:-1.0.0}"
SOURCE="${2:-dist/Giperion}"
OUTPUT="${3:-dist}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
case "$SOURCE" in /*) SRC="$SOURCE" ;; *) SRC="$ROOT/$SOURCE" ;; esac
case "$OUTPUT" in /*) OUT="$OUTPUT" ;; *) OUT="$ROOT/$OUTPUT" ;; esac
WORK="$ROOT/build/appimage"
APPDIR="$WORK/Giperion.AppDir"

if ! command -v appimagetool >/dev/null 2>&1; then
  echo "appimagetool не найден: https://github.com/AppImage/AppImageKit"
  exit 1
fi

rm -rf "$WORK"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/lib/giperion"
cp -a "$SRC/." "$APPDIR/usr/lib/giperion/"

cat > "$APPDIR/AppRun" <<'EOF'
#!/usr/bin/env bash
# Giperion: данные, логи и архив — в профиль пользователя.
# GIPERION_HOME не трогаем: от него зависит поиск assets/skins в AppImage.
HERE="$(dirname "$(readlink -f "$0")")"
GI_HOME="${GIPERION_STATE_DIR:-$HOME/.local/share/giperion}"
export GIPERION_DATA_DIR="${GIPERION_DATA_DIR:-$GI_HOME/data}"
export GIPERION_LOGS_DIR="${GIPERION_LOGS_DIR:-$GI_HOME/logs}"
export GIPERION_ARCHIVE_DIR="${GIPERION_ARCHIVE_DIR:-$GI_HOME/archive}"

mkdir -p "$GIPERION_DATA_DIR" "$GIPERION_LOGS_DIR" "$GIPERION_ARCHIVE_DIR"
if [ ! -f "$GIPERION_DATA_DIR/intents.json" ] && [ -f "$HERE/usr/lib/giperion/_internal/data/intents.json" ]; then
  cp "$HERE/usr/lib/giperion/_internal/data/intents.json" "$GIPERION_DATA_DIR/" 2>/dev/null || true
fi

exec "$HERE/usr/lib/giperion/Giperion" "$@"
EOF
chmod 755 "$APPDIR/AppRun"

cp "$ROOT/packaging/linux/giperion.desktop" "$APPDIR/giperion.desktop"

if [ -f "$ROOT/assets/icon.png" ]; then
  cp "$ROOT/assets/icon.png" "$APPDIR/giperion.png"
fi

mkdir -p "$OUT"
ARCH=x86_64 appimagetool "$APPDIR" \
  "$OUT/Giperion-${VERSION}-linux-x64.AppImage"

echo "Собрано: $OUT/Giperion-${VERSION}-linux-x64.AppImage"
