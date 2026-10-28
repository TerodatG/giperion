# Giperion/terminal/core/update_types.py                             v001
# Типы обновлений: выпуск, каталог, итог проверки и установки.

from dataclasses import dataclass, field
from pathlib import Path


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
