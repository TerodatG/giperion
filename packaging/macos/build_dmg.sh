#!/usr/bin/env bash
# Giperion/packaging/macos/build_dmg.sh                              v001
# Собирает .dmg и zip из PyInstaller .app (запускать на macOS).
# Usage: bash packaging/macos/build_dmg.sh 1.0.0 dist/Giperion.app dist

set -euo pipefail

VERSION="${1:-1.0.0}"
SOURCE="${2:-dist/Giperion.app}"
OUTPUT="${3:-dist}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
case "$SOURCE" in /*) APP="$SOURCE" ;; *) APP="$ROOT/$SOURCE" ;; esac
case "$OUTPUT" in /*) OUT="$OUTPUT" ;; *) OUT="$ROOT/$OUTPUT" ;; esac

if [ ! -d "$APP" ]; then
  echo "Нет .app: $APP"
  exit 1
fi

mkdir -p "$OUT"

ditto -c -k --sequesterRsrc --keepParent "$APP" \
  "$OUT/Giperion-${VERSION}-macos.zip"

hdiutil create -volname "Giperion" -srcfolder "$APP" \
  -ov -format UDZO \
  "$OUT/Giperion-${VERSION}-macos.dmg"

echo "Собрано: $OUT/Giperion-${VERSION}-macos.{dmg,zip}"
