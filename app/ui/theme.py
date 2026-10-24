# Giperion/app/ui/theme.py                                         v004
# Общие константы оформления окна: цвета, шрифты, тайминги, печать.
# Последнее изменение: цвета трёх сенаторов.

BOT_NAME = "Гиперион"
BOT_NICKNAME = "Giperion"

# Гарнитура и размер шрифта истории чата по умолчанию.
DEFAULT_CHAT_FONT_FAMILY = ""
DEFAULT_CHAT_FONT_SIZE = 11
MIN_CHAT_FONT_SIZE = 8
MAX_CHAT_FONT_SIZE = 28

# Цвета текста под тёмную футуристическую тему: зелёный терминальный
# лог на почти чёрном экране, как в «Коде доступа рай».
USER_COLOR = "#c9efc0"
BOT_COLOR = "#7cf58f"
PARAMETERS_COLOR = "#7fd8f0"
VARIABLES_COLOR = "#ffd479"
SYSTEM_COLOR = "#ffc857"
LEVEL_UP_COLOR = "#ff8ae8"
DATA_COLOR = "#8fd8c8"
EXTERNAL_COLOR = "#9ad7ff"
SENATOR_COLORS = {
    "senator1": "#ffd479",
    "senator2": "#e0a8ff",
    "senator3": "#7fd8b0",
}
COPY_COLOR = "#6fe08a"

# Цвет значка «редактировать» и отпечатков времени в сообщениях.
EDIT_COLOR = "#ffd479"
STAMP_COLOR = "#5f9a6a"

# Формат времени сообщения: дата, часы и минуты.
STAMP_FORMAT = "%d.%m.%Y %H:%M"

# Пауза перед ответом ядра и шаг анимации индикатора «обрабатываю запрос».
THINKING_DELAY_MS = 1000
THINKING_STEP_MS = 300
THINKING_DOTS = 4

# Подпись индикатора ожидания ответа.
THINKING_TEXT = "обрабатываю запрос"

# Как часто окно проверяет, готов ли ответ внешней модели.
ANSWER_POLL_MS = 80

# Эмуляция печати: шаг таймера и доступные скорости (символов в секунду).
TYPING_STEP_MS = 25
TYPING_SPEEDS = (
    (15, "Медленно — 15 симв/с"),
    (35, "Обычно — 35 симв/с"),
    (70, "Быстро — 70 симв/с"),
    (140, "Очень быстро — 140 симв/с"),
)

# Толщина невидимой рамки безрамочного окна, за которую тянем мышью.
WINDOW_EDGE_MARGIN = 7

# Палитра цветов текста, которую можно менять в настройках.
# «message» — цвет важных сообщений (плашка нового уровня),
# «data» — текст из файлов и интернета,
# «external» — ответы внешних моделей.
DEFAULT_COLORS = {
    "system": SYSTEM_COLOR,
    "bot": BOT_COLOR,
    "user": USER_COLOR,
    "message": LEVEL_UP_COLOR,
    "data": DATA_COLOR,
    "external": EXTERNAL_COLOR,
    **SENATOR_COLORS,
}

# CSS-фрагменты для видов шрифта, которые выбираются в окне «Вид».
TEXT_STYLE_CSS = {
    "normal": "",
    "bold": "font-weight:bold;",
    "italic": "font-style:italic;",
    "bold_italic": "font-weight:bold; font-style:italic;",
}
