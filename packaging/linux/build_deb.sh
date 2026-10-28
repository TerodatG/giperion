#!/usr/bin/env bash
# Giperion/packaging/linux/build_deb.sh                              v001
# Собирает .deb из one-dir сборки PyInstaller.
# Usage: bash packaging/linux/build_deb.sh 1.0.0 dist/Giperion dist

set -euo pipefail

VERSION="${1:-1.0.0}"
SOURCE="${2:-dist/Giperion}"
OUTPUT="${3:-dist}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
case "$SOURCE" in /*) SRC="$SOURCE" ;; *) SRC="$ROOT/$SOURCE" ;; esac
case "$OUTPUT" in /*) OUT="$OUTPUT" ;; *) OUT="$ROOT/$OUTPUT" ;; esac
WORK="$ROOT/build/deb"
PACKAGE="$WORK/giperion_${VERSION}_amd64"

rm -rf "$WORK"
mkdir -p "$PACKAGE/DEBIAN" \
  "$PACKAGE/usr/lib/giperion" \
  "$PACKAGE/usr/bin" \
  "$PACKAGE/usr/share/applications" \
  "$PACKAGE/usr/share/icons/hicolor/256x256/apps"

cp -a "$SRC/." "$PACKAGE/usr/lib/giperion/"

cat > "$PACKAGE/usr/bin/giperion" <<'EOF'
#!/usr/bin/env bash
# Giperion: данные, логи и архив — в профиль пользователя.
# GIPERION_HOME не трогаем: от него зависит поиск assets/skins в пакете.
GI_HOME="${GIPERION_STATE_DIR:-$HOME/.local/share/giperion}"
export GIPERION_DATA_DIR="${GIPERION_DATA_DIR:-$GI_HOME/data}"
export GIPERION_LOGS_DIR="${GIPERION_LOGS_DIR:-$GI_HOME/logs}"
export GIPERION_ARCHIVE_DIR="${GIPERION_ARCHIVE_DIR:-$GI_HOME/archive}"

mkdir -p "$GIPERION_DATA_DIR" "$GIPERION_LOGS_DIR" "$GIPERION_ARCHIVE_DIR"
if [ ! -f "$GIPERION_DATA_DIR/intents.json" ] && [ -f /usr/lib/giperion/_internal/data/intents.json ]; then
  cp /usr/lib/giperion/_internal/data/intents.json "$GIPERION_DATA_DIR/" 2>/dev/null || true
fi

exec /usr/lib/giperion/Giperion "$@"
EOF
chmod 755 "$PACKAGE/usr/bin/giperion"

cp "$ROOT/packaging/linux/giperion.desktop" \
  "$PACKAGE/usr/share/applications/giperion.desktop"

if [ -f "$ROOT/assets/icon.png" ]; then
  cp "$ROOT/assets/icon.png" \
    "$PACKAGE/usr/share/icons/hicolor/256x256/apps/giperion.png"
fi

cat > "$PACKAGE/DEBIAN/control" <<EOF
Package: giperion
Version: $VERSION
Section: devel
Priority: optional
Architecture: amd64
Maintainer: Giperion <noreply@example.com>
Depends: libgl1, libegl1, libdbus-1-3, libfontconfig1, libxkbcommon-x11-0, libxcb-cursor0, libxcb-icccm4, libxcb-image0, libxcb-keysyms1, libxcb-render-util0, libxcb-shape0, libxcb-xinerama0, libxcb-xkb1
Description: Giperion AI coding agent
 Local terminal, agent, knowledge base and Giperion model.
EOF

mkdir -p "$OUT"
dpkg-deb --root-owner-group --build "$PACKAGE" \
  "$OUT/Giperion-${VERSION}-linux-x64.deb"

echo "Собрано: $OUT/Giperion-${VERSION}-linux-x64.deb"
