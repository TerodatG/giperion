# Giperion/terminal/core/update_service.py                          v001
# Проверка, скачивание и установка обновлений терминала.
# Последнее изменение: первый вариант — каталог выпусков и патчи-архивы.

import hashlib
import json
import os
import re
import shutil
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from config import BASE_DIR, DATA_DIR
from terminal.core.app_version import (
    APP_NAME,
    current_released,
    current_version,
    is_newer,
    set_installed,
    version_key,
)
from terminal.core.update_channel import feed_source

# Каталог выпусков: локальный файл, пока у проекта нет своего сервера.
FEED_FILE = DATA_DIR / "releases.json"

# Сюда качаются патчи и сюда же складываются резервные копии.
UPDATES_DIR = BASE_DIR / "updates"
PATCH_PREFIX = "giperion"

# Корень проекта, который обновляет патч (в тестах подменяется).
PROJECT_ROOT = BASE_DIR

# Ограничения, чтобы патч не съел память и диск.
DOWNLOAD_TIMEOUT = 30
MAX_PATCH_BYTES = 1024 * 1024 * 1024

# Папки, которые патч трогать не имеет права.
FORBIDDEN_PREFIXES = (".git", "updates", "logs", "__pycache__")

_CHUNK_SIZE = 256 * 1024


class UpdateError(Exception):
    """Понятная человеку ошибка обновления."""


@dataclass
class Release:
    """Один выпуск терминала из каталога."""

    version: str
    date: str = ""
    title: str = ""
    notes: list[str] = field(default_factory=list)
    patch: str = ""
    sha256: str = ""
    size: int = 0

    @property
    def has_patch(self) -> bool:
        """Есть ли у выпуска файл патча."""

        return bool(self.patch)

    @property
    def note_text(self) -> str:
        """Короткая подпись выпуска для списков."""

        return f"{self.version} от {self.date}" if self.date else self.version


@dataclass
class Feed:
    """Каталог выпусков и подпись его источника."""

    releases: list[Release] = field(default_factory=list)
    source: str = ""
    channel: str = "stable"
    updated: str = ""


@dataclass
class UpdateCheck:
    """Результат проверки обновлений."""

    current: str = ""
    released: str = ""
    channel: str = ""
    source: str = ""
    updated: str = ""
    releases: list[Release] = field(default_factory=list)
    new_releases: list[Release] = field(default_factory=list)
    error: str = ""

    @property
    def up_to_date(self) -> bool:
        """Установлена ли самая свежая версия."""

        return not self.new_releases and not self.error

    @property
    def available(self) -> Release | None:
        """Самый свежий из доступных выпусков."""

        return self.new_releases[0] if self.new_releases else None


@dataclass
class DownloadedPatch:
    """Скачанный патч в папке updates."""

    path: Path
    version: str
    size: int = 0
    sha256: str = ""
    source: str = ""


@dataclass
class ApplyResult:
    """Итог установки патча."""

    version: str
    files: list[str] = field(default_factory=list)
    backup_dir: Path | None = None
    requires_restart: bool = True


# --- Каталог выпусков ---


def _safe_name(text: str) -> str:
    """Оставляет в имени файла только безопасные символы."""

    cleaned = re.sub(r"[^0-9A-Za-z._-]+", "-", str(text or ""))
    cleaned = re.sub(r"\.{2,}", ".", cleaned).strip("-._")

    return cleaned or "release"


def patch_file_name(release: Release) -> str:
    """Имя патча: версия и дата прямо в названии файла."""

    released = _safe_name(release.date) or date.today().isoformat()

    return f"{PATCH_PREFIX}-{_safe_name(release.version)}-{released}.patch"


def _absolute(path: Path | str) -> Path:
    """Дополняет относительный путь до папки проекта."""

    candidate = Path(path)

    return candidate if candidate.is_absolute() else BASE_DIR / candidate


def _read_source(source: str) -> tuple[str, str]:
    """Возвращает текст каталога и подпись источника."""

    source = (source or "").strip()

    if source.startswith(("http://", "https://")):
        request = urllib.request.Request(
            source,
            headers={
                "User-Agent": f"{APP_NAME}/{current_version()}",
            },
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=DOWNLOAD_TIMEOUT,
            ) as response:
                return (
                    response.read().decode("utf-8"),
                    source,
                )
        except (urllib.error.URLError, OSError) as error:
            raise UpdateError(
                f"каталог выпусков недоступен: {error}"
            ) from error

    path = _absolute(source) if source else FEED_FILE

    try:
        return (
            path.read_text(encoding="utf-8"),
            f"каталог {path.name}",
        )
    except OSError as error:
        raise UpdateError(
            f"каталог выпусков не найден: {path.name}"
        ) from error
    except UnicodeDecodeError as error:
        raise UpdateError(
            "каталог выпусков повреждён: не читается как текст"
        ) from error


def _release_from(item: dict) -> Release | None:
    """Собирает выпуск из записи каталога, терпя лишние поля."""

    if not isinstance(item, dict):
        return None

    version = str(item.get("version") or "").strip()

    if not version:
        return None

    notes = item.get("notes") or []

    if isinstance(notes, str):
        notes = [notes]

    return Release(
        version=version,
        date=str(item.get("date") or "").strip(),
        title=str(item.get("title") or "").strip(),
        notes=[str(note) for note in notes if str(note).strip()],
        patch=str(item.get("patch") or "").strip(),
        sha256=str(item.get("sha256") or "").strip(),
        size=int(item.get("size") or 0),
    )


def load_feed(source: str = "") -> Feed:
    """Читает каталог выпусков: локальный файл или адрес в сети."""

    text, label = _read_source(source)

    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        raise UpdateError(
            "каталог выпусков повреждён: это не JSON"
        ) from error

    if not isinstance(document, dict):
        raise UpdateError("каталог выпусков повреждён: ожидался объект")

    releases = []

    for item in document.get("releases") or []:
        release = _release_from(item)

        if release is not None:
            releases.append(release)

    # Свежие выпуски — первыми.
    releases.sort(key=lambda item: version_key(item.version), reverse=True)

    if not releases:
        raise UpdateError("в каталоге нет ни одного выпуска")

    return Feed(
        releases=releases,
        source=label,
        channel=str(document.get("channel") or "stable"),
        updated=str(document.get("updated") or ""),
    )


def load_feed_any(source: str = "") -> Feed:
    """Читает канал; если он недоступен — локальный каталог выпусков."""

    try:
        return load_feed(source or feed_source())
    except UpdateError:
        if source:
            raise

        return load_feed("")


def check_for_updates(source: str = "") -> UpdateCheck:
    """Сравнивает установленную версию с каталогом выпусков."""

    check = UpdateCheck(
        current=current_version(),
        released=current_released(),
    )

    try:
        feed = load_feed(source)
    except UpdateError as error:
        check.error = str(error)

        return check

    check.source = feed.source
    check.channel = feed.channel
    check.updated = feed.updated
    check.releases = feed.releases
    check.new_releases = [
        release
        for release in feed.releases
        if is_newer(release.version, check.current)
    ]

    return check


def check_updates(source: str = "") -> UpdateCheck:
    """Проверяет канал; если он недоступен — локальный каталог выпусков."""

    check = check_for_updates(source or feed_source())

    if check.error and not source:
        local = check_for_updates("")

        if not local.error:
            return local

    return check


def release_for(version: str, releases: list[Release]) -> Release | None:
    """Находит выпуск по версии."""

    key = version_key(version)

    for release in releases:
        if version_key(release.version) == key:
            return release

    return None


# --- Скачивание ---


def _sha256(path: Path) -> str:
    """Считает контрольную сумму файла."""

    digest = hashlib.sha256()

    with path.open("rb") as file:
        for block in iter(lambda: file.read(_CHUNK_SIZE), b""):
            digest.update(block)

    return digest.hexdigest()


def _resolve_local(patch: str) -> Path:
    """Ищет файл патча рядом с проектом или каталогом выпусков."""

    candidate = Path(patch)

    if candidate.is_absolute():
        return candidate

    for option in (
        BASE_DIR / candidate,
        FEED_FILE.parent / candidate,
        UPDATES_DIR / candidate,
    ):
        if option.is_file():
            return option

    return BASE_DIR / candidate


def _download_remote(url: str, destination: Path) -> None:
    """Скачивает патч по сети во временный файл."""

    request = urllib.request.Request(
        url,
        headers={"User-Agent": f"{APP_NAME}/{current_version()}"},
    )

    received = 0

    try:
        with urllib.request.urlopen(
            request,
            timeout=DOWNLOAD_TIMEOUT,
        ) as response, destination.open("wb") as file:
            while True:
                block = response.read(_CHUNK_SIZE)

                if not block:
                    break

                received += len(block)

                if received > MAX_PATCH_BYTES:
                    raise UpdateError("патч больше допустимого размера")

                file.write(block)
    except (urllib.error.URLError, OSError) as error:
        raise UpdateError(f"не удалось скачать патч: {error}") from error


def download_update(
    release: Release,
    directory: Path | str | None = None,
) -> DownloadedPatch:
    """Скачивает патч выпуска в папку updates под именем с версией и датой."""

    if not release.has_patch:
        raise UpdateError(
            "в выпуске не указан файл патча — скачивать нечего"
        )

    target_dir = Path(directory or UPDATES_DIR)
    target_dir.mkdir(parents=True, exist_ok=True)

    target = target_dir / patch_file_name(release)
    temporary = target.with_name(target.name + ".part")
    temporary.unlink(missing_ok=True)

    try:
        if release.patch.startswith(("http://", "https://")):
            _download_remote(release.patch, temporary)
        else:
            source = _resolve_local(release.patch)

            if not source.is_file():
                raise UpdateError(
                    f"файл патча не найден: {release.patch}"
                )

            if source.stat().st_size > MAX_PATCH_BYTES:
                raise UpdateError("патч больше допустимого размера")

            shutil.copyfile(source, temporary)

        digest = _sha256(temporary)

        if release.sha256 and digest.lower() != release.sha256.lower():
            raise UpdateError(
                "контрольная сумма патча не совпала"
            )

        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)

    return DownloadedPatch(
        path=target,
        version=release.version,
        size=target.stat().st_size,
        sha256=digest,
        source=release.patch,
    )


# --- Установка ---


def _safe_relative(name: str) -> Path | None:
    """Проверяет путь внутри патча: без выхода за папку проекта."""

    clean = str(name or "").replace("\\", "/").strip("/")

    if not clean:
        return None

    relative = Path(clean)

    if relative.is_absolute():
        return None

    if any(part == ".." for part in relative.parts):
        return None

    if ":" in relative.parts[0]:
        return None

    lowered = tuple(part.lower() for part in relative.parts)

    if lowered[0] in FORBIDDEN_PREFIXES:
        return None

    return relative


def _is_symlink(member: zipfile.ZipInfo) -> bool:
    """Отличает ссылку в архиве от обычного файла."""

    return (member.external_attr >> 16) & 0o170000 == 0o120000


def _extract_patch(
    patch: Path,
    release: Release,
) -> tuple[list[str], Path | None]:
    """Распаковывает архив поверх проекта, сохраняя старые файлы."""

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = UPDATES_DIR / "backup" / (
        f"{_safe_name(release.version)}-{stamp}"
    )

    applied: list[str] = []
    backed_up = 0
    total_size = 0

    with zipfile.ZipFile(patch) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue

            if _is_symlink(member):
                raise UpdateError(
                    f"в патче есть ссылка: {member.filename}"
                )

            relative = _safe_relative(member.filename)

            if relative is None:
                raise UpdateError(
                    f"недопустимый путь в патче: {member.filename}"
                )

            total_size += member.file_size

            if total_size > MAX_PATCH_BYTES:
                raise UpdateError(
                    "патч распаковывается в слишком большой объём"
                )

            destination = PROJECT_ROOT / relative

            if destination.is_file():
                backup = backup_root / relative
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(destination, backup)
                backed_up += 1

            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.read(member))

            applied.append(relative.as_posix())

    return sorted(applied), (backup_root if backed_up else None)


def apply_update(
    patch: Path | str,
    release: Release,
) -> ApplyResult:
    """Устанавливает скачанный патч и запоминает новую версию."""

    path = Path(patch)

    if not path.is_file():
        raise UpdateError(
            "файл патча не найден — скачай обновление заново"
        )

    digest = _sha256(path)

    if release.sha256 and digest.lower() != release.sha256.lower():
        raise UpdateError(
            "контрольная сумма патча не совпала — скачай его заново"
        )

    if not zipfile.is_zipfile(path):
        raise UpdateError(
            "патч не является архивом — такой выпуск устанавливают вручную"
        )

    files, backup_dir = _extract_patch(path, release)

    if not files:
        raise UpdateError("в патче нет файлов для установки")

    set_installed(
        release.version,
        release.date,
        patch=path.name,
        note=release.title,
    )

    return ApplyResult(
        version=release.version,
        files=files,
        backup_dir=backup_dir,
        requires_restart=True,
    )
