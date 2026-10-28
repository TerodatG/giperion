#!/usr/bin/env bash
# Giperion/packaging/linux/build_appimage.sh                         v001
# Собирает AppImage из one-dir сборки PyInstaller (нужен appimagetool).
# Usage: bash packaging/linux/build_appimage.sh 1.0.0 dist/Giperion dist

set -euo pipefail

VERSION="${1:-1.0.0}"
SOURCE="${2:-dist/Giperion}"
OUTPUT="${3:-dist}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WORK="$ROOT/build/appimage"
APPDIR="$WORK/Giperion.AppDir"

if ! command -v appimagetool >/dev/null 2>&1; then
  echo "appimagetool не найден: https://github.com/AppImage/AppImageKit"
  exit 1
fi

rm -rf "$WORK"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/lib/giperion"
cp -a "$ROOT/$SOURCE/." "$APPDIR/usr/lib/giperion/"

cat > "$APPDIR/AppRun" <<'EOF'
#!/usr/bin/env bash
exec "$(dirname "$0")/usr/lib/giperion/Giperion" "$@"
EOF
chmod 755 "$APPDIR/AppRun"

cp "$ROOT/packaging/linux/giperion.desktop" "$APPDIR/giperion.desktop"

if [ -f "$ROOT/assets/icon.png" ]; then
  cp "$ROOT/assets/icon.png" "$APPDIR/giperion.png"
fi

mkdir -p "$ROOT/$OUTPUT"
ARCH=x86_64 appimagetool "$APPDIR" \
  "$ROOT/$OUTPUT/Giperion-${VERSION}-linux-x64.AppImage"

echo "Собрано: $OUTPUT/Giperion-${VERSION}-linux-x64.AppImage"
