# Giperion/app/ui/dialog_text.py                                  v002
# HTML-тексты для вложенных окон «Справка», «Умения» и «Обновление».
# Последнее изменение: журнал выпусков терминала.

def build_help_html(sections: list[tuple[str, list[str]]]) -> str:
    """Собирает HTML-справку: разделы и список команд."""

    def escape(text: str) -> str:
        """Экранирует угловые скобки в шаблонах команд."""

        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    blocks = []

    for number, (title, items) in enumerate(sections):
        top = "0" if number == 0 else "16px"

        rows = "".join(
            f'<p style="margin:0 0 5px 0;">'
            f'<span style="color:#d09a6a;">▸</span> '
            f'<span style="color:#c8ecc0;">{escape(item)}</span></p>'
            for item in items
        )

        header = ""

        if title:
            header = (
                f'<p style="margin:{top} 0 7px 0;">'
                f'<b style="color:#ffb37a;">{escape(title.upper())}</b></p>'
            )

        blocks.append(f"{header}{rows}")

    return "".join(blocks)


def build_skills_html(skills: list[dict]) -> str:
    """Собирает HTML-список навыков для окна «Умения»."""

    rows = []

    for number, skill in enumerate(skills, start=1):
        rows.append(
            f'<p style="margin:0 0 12px 0;">'
            f'<span style="color:#d09a6a;">{number:02d}</span> '
            f'<b style="color:#7cf58f;">{skill["name"]}</b><br>'
            f'<span style="color:#9fbfa5;">{skill["description"]}</span>'
            f'</p>'
        )

    return "".join(rows)


def format_release_date(text: str) -> str:
    """Пишет дату выпуска по-русски: 01.11.2026."""

    parts = str(text or "").strip().split("-")

    if len(parts) == 3 and all(part.isdigit() for part in parts):
        return f"{parts[2]}.{parts[1]}.{parts[0]}"

    return str(text or "").strip()


def build_updates_html(entries: list[dict]) -> str:
    """Собирает журнал выпусков для зелёного поля окна «Обновление».

    Записи идут от свежей к старой. Новая запись помечается значком
    «НОВОЕ», чтобы после проверки было видно, что именно изменилось.
    """

    def escape(text: str) -> str:
        """Экранирует угловые скобки и амперсанды в тексте выпуска."""

        return (
            str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    blocks = []

    for entry in entries:
        version = escape(entry.get("version") or "")
        released = format_release_date(entry.get("date") or "")
        title = escape(entry.get("title") or "")
        notes = entry.get("notes") or []
        is_new = bool(entry.get("is_new"))

        badge = ""

        if is_new:
            badge = (
                '<span style="background-color:#7cf58f; color:#05100a;">'
                "&nbsp;НОВОЕ&nbsp;</span>"
            )

        header = (
            f'<p style="margin:0 0 4px 0;">'
            f'<b style="color:#7cf58f; font-size:13pt;">{version}</b> '
            f'<span style="color:#d09a6a;">· {released}</span> {badge}</p>'
        )

        heading = ""

        if title:
            heading = (
                f'<p style="margin:0 0 7px 0;">'
                f'<b style="color:#ffb37a;">{title.upper()}</b></p>'
            )

        rows = "".join(
            f'<p style="margin:0 0 5px 0;">'
            f'<span style="color:#d09a6a;">▸</span> '
            f'<span style="color:#c8ecc0;">{escape(note)}</span></p>'
            for note in notes
        )

        if blocks:
            blocks.append(
                '<p style="margin:14px 0 12px 0; color:#23421f;">'
                + "─" * 46
                + "</p>"
            )

        blocks.append(f"{header}{heading}{rows}")

    return "".join(blocks)
