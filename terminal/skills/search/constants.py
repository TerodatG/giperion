# Giperion/app/skills/search/constants.py                         v001
# Настройки поиска: адреса, команды, таймауты и слова-исключения.
# Последнее изменение: выделено из web_search.

SEARCH_TIMEOUT = 15

# По этому префиксу окно отличает найденное в сети от обычного ответа.
INTERNET_ANSWER_PREFIX = "Вот что нашлось в интернете"

# Команды, после которых остаток сообщения считается поисковым запросом.
SEARCH_COMMANDS = (
    "найди в интернете",
    "поищи в интернете",
    "посмотри в интернете",
    "поиск в интернете",
    "что пишут в интернете",
    "найди в сети",
    "поищи в сети",
    "погугли",
    "загугли",
)

BING_URL = "https://www.bing.com/search?q="
BING_RSS_URL = "https://www.bing.com/search?format=rss&q="
WIKIPEDIA_API = (
    "https://ru.wikipedia.org/w/api.php?action=query&list=search"
    "&format=json&utf8=1&srlimit=3&srsearch="
)

# Запросы о свежих данных не подменяем статьями из энциклопедии.
LIVE_QUERY_WORDS = (
    "погод",
    "прогноз",
    "курс",
    "цен",
    "сегодня",
    "сейчас",
    "новост",
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)
