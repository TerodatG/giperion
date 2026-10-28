#!/usr/bin/env bash
# Giperion/packaging/linux/build_deb.sh                              v001
# Собирает .deb из one-dir сборки PyInstaller.
# Usage: bash packaging/linux/build_deb.sh 1.0.0 dist/Giperion dist

set -euo pipefail

VERSION="${1:-1.0.0}"
SOURCE="${2:-dist/Giperion}"
OUTPUT="${3:-dist}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WORK="$ROOT/build/deb"
PACKAGE="$WORK/giperion_${VERSION}_amd64"

rm -rf "$WORK"
mkdir -p "$PACKAGE/DEBIAN" \
  "$PACKAGE/usr/lib/giperion" \
  "$PACKAGE/usr/bin" \
  "$PACKAGE/usr/share/applications" \
  "$PACKAGE/usr/share/icons/hicolor/256x256/apps"

cp -a "$ROOT/$SOURCE/." "$PACKAGE/usr/lib/giperion/"

cat > "$PACKAGE/usr/bin/giperion" <<'EOF'
#!/usr/bin/env bash
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
Description: Giperion AI coding agent
 Local terminal, agent, knowledge base and Giperion model.
EOF

mkdir -p "$ROOT/$OUTPUT"
dpkg-deb --build "$PACKAGE" \
  "$ROOT/$OUTPUT/Giperion-${VERSION}-linux-x64.deb"

echo "Собрано: $OUTPUT/Giperion-${VERSION}-linux-x64.deb"
