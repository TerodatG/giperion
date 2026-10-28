#!/usr/bin/env bash
# Giperion/packaging/macos/build_dmg.sh                              v001
# Собирает .dmg и zip из PyInstaller .app (запускать на macOS).
# Usage: bash packaging/macos/build_dmg.sh 1.0.0 dist/Giperion.app dist

set -euo pipefail

VERSION="${1:-1.0.0}"
SOURCE="${2:-dist/Giperion.app}"
OUTPUT="${3:-dist}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
APP="$ROOT/$SOURCE"

if [ ! -d "$APP" ]; then
  echo "Нет .app: $APP"
  exit 1
fi

mkdir -p "$ROOT/$OUTPUT"

ditto -c -k --sequesterRsrc --keepParent "$APP" \
  "$ROOT/$OUTPUT/Giperion-${VERSION}-macos.zip"

hdiutil create -volname "Giperion" -srcfolder "$APP" \
  -ov -format UDZO \
  "$ROOT/$OUTPUT/Giperion-${VERSION}-macos.dmg"

echo "Собрано: $OUTPUT/Giperion-${VERSION}-macos.{dmg,zip}"
