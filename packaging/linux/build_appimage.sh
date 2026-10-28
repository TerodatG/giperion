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
# Giperion: данные и логи — в профиль пользователя, модели — из AppImage.
HERE="$(dirname "$(readlink -f "$0")")"
export GIPERION_HOME="${GIPERION_HOME:-$HOME/.local/share/giperion}"
export GIPERION_MODELS_DIR="${GIPERION_MODELS_DIR:-$HERE/usr/lib/giperion/_internal/models}"

DATA="$GIPERION_HOME/data"
mkdir -p "$DATA"
if [ ! -f "$DATA/intents.json" ] && [ -f "$HERE/usr/lib/giperion/_internal/data/intents.json" ]; then
  cp "$HERE/usr/lib/giperion/_internal/data/intents.json" "$DATA/" 2>/dev/null || true
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
