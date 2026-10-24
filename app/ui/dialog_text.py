# Giperion/app/ui/dialog_text.py                                  v001
# HTML-тексты для вложенных окон «Справка» и «Умения».
# Последнее изменение: выделено из gui.py.

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
