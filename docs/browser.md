# Браузер с JavaScript (Playwright)

Инструменты `browser_read` и `browser_act` открывают страницу в
headless Chromium, ждут выполнения скриптов и возвращают текст. Нужны
там, где `fetch_url` видит пустой каркас: SPA, ленты, таблицы,
подгружаемые через JS.

```
browser_read(url="https://quotes.toscrape.com/js/")
browser_read(url="https://example.com/app", wait="#content")

browser_act(
    url="https://quotes.toscrape.com/js/",
    actions=[{"type": "click", "selector": "li.next a"}],
    shot=True,
)
```

Действия `browser_act` (до 10 за вызов):

| Тип | Поля | Что делает |
|---|---|---|
| `click` | `selector` | клик по элементу |
| `fill` | `selector`, `text` | ввод текста |
| `press` | `selector`, `key` | нажатие клавиши |
| `hover` | `selector` | наведение |
| `select` | `selector`, `value` | выбор в `<select>` |
| `scroll` | `pixels` | прокрутка страницы |
| `wait` | `ms` | пауза |
| `goto` | `url` | переход на другой адрес в том же браузере |
| `back` | — | назад по истории |
| `download` | `selector` | скачать файл по клику (до 10 МБ) |

`full_page=True` сохраняет скриншот всей страницы, а не только экрана.
Скачанные файлы кладутся в `data/agent_browser/downloads/`, путь
возвращается в ответе строкой «файлы: …».

## Сессия на задачу

По умолчанию Chromium запускается один раз и живёт до конца задачи
(`browser_session`, галочка «Одна сессия браузера на задачу»). Поэтому:

- `browser_act(url="current", actions=[...])` действует на уже открытой
  странице без нового перехода;
- `browser_read(url="current")` читает текущую страницу;
- cookies и localStorage сохраняются в
  `data/agent_browser/profile.json` и подхватываются следующей задачей;
  удалите файл, чтобы сбросить авторизацию;
- после задачи сессия закрывается, простой браузер — через 5 минут.

Замеры: первое открытие `example.com` 3.5 с, повторное 1.5 с, клик по
текущей странице 0.87 с, чтение без перехода — мгновенно.

Ответ:

```
источник: https://quotes.toscrape.com/js/page/2/
заголовок: Quotes to Scrape

… текст страницы …

скриншот: data/agent_browser/1793026248-17bb1a28ce.png
```

## Установка

```powershell
python -m pip install playwright
python -m playwright install chromium
```

Пакет занимает десятки мегабайт, браузеры Chromium — около 700 МБ
(в `%LOCALAPPDATA%\ms-playwright`). Без установленного Chromium
инструмент вернёт понятную ошибку, а не упадёт.

## Включение

В окне «Провайдер…» — галочка **«Браузер с JavaScript (Playwright)»**
(`browser_js_enabled`, по умолчанию выключена). Инструмент имеет
`risk=exec`, поэтому каждое открытие требует подтверждения; разрешение
запоминается по домену (`web:<host>`) до конца задачи — так же, как у
`fetch_url`.

## Как это устроено

1. Агент проверяет адрес теми же правилами, что `fetch_url`:
   только `http`/`https`, порты 80/443, запрет localhost и приватных
   сетей (резолвятся все адреса хоста).
2. Запускается отдельный процесс
   `python -m terminal.core.agent.browser_worker` с JSON-запросом.
   Внутри — Playwright, headless Chromium, `accept_downloads=False`.
3. `page.goto(wait_until="domcontentloaded")`, затем пауза 1.2 с или
   ожидание CSS-селектора `wait`; после этого берутся `title` и
   `inner_text("body")`.
4. Все сетевые запросы страницы проходят через `page.route`: запросы к
   локальным и приватным хостам и не-http(s) схемам обрываются, даже
   если их инициировал JS (защита от SSRF). WebSocket-соединения
   проверяются через `route_web_socket`, если версия Playwright это
   поддерживает.
5. Проверяется `robots.txt` домена (кэш 5 минут): запрещённый путь не
   открывается. Между запросами к одному домену — пауза не меньше
   1.5 с.
6. Родитель ждёт воркер не дольше `timeout + 20` с, текст обрезается до
   12 000 символов, процесс браузера всегда закрывается.
7. `browser_act` выполняет действия по очереди; при `shot=True`
   скриншот кладётся в `data/agent_browser/`, путь возвращается в ответе.

## Настройки и лимиты

| Что | Значение |
|---|---|
| Таймаут навигации | 60 с по умолчанию, можно передать `timeout` (5–120) |
| Ожидание JS | `wait` — CSS-селектор; иначе пауза 1.2 с |
| Действия | до 12 за вызов: click, fill, press, hover, select, scroll, wait, wait_text, wait_url, goto, back, download, new_tab, switch_tab, close_tab |
| Сессия | один Chromium на задачу, `url="current"` для открытой страницы |
| Пул | живой Chromium переиспользуется между задачами, простой 5 мин |
| Память | `--max-old-space-size=512`, GPU отключён |
| Текст | до 12 000 символов |
| Браузер | сессия с профилем `data/agent_browser/profile.json` |
| Сеть | только публичные http(s)-хосты, robots.txt и пауза 1.5 с |
| Скриншот | `data/agent_browser/*.png`, вне git |

## Проверено

- `https://quotes.toscrape.com/js/` — 10 цитат, которых нет в исходном
  HTML: страница отрендерена, текст получен за 4.2 с.
- `https://example.com` — 2.5 с, заголовок и текст.
- `http://127.0.0.1:8000/` — отказ («Разрешены только порты 80 и 443»).
- Живая задача на `qwen3-coder-30b`: модель сама вызвала
  `browser_read`, получила страницу и назвала автора первой цитаты за
  15.5 с, с подтверждением.
- `browser_act` с кликом по `li.next a`: страница 2 цитат, 6.3 с,
  скриншот 5 КБ в `data/agent_browser/`.
- Сценарий click → back → hover за 8.6 с: вернулись на первую страницу,
  полноэкранный скриншот 99 КБ.

## Ограничения

- Сессия держит один Chromium на задачу; между задачами он закрывается,
  а cookies/localStorage переносятся через
  `data/agent_browser/profile.json`.
- Вкладки поддерживаются действиями `new_tab`, `switch_tab` и
  `close_tab`.
- Скачанный PDF по возможности разбирается `pypdf` и его текст
  добавляется в ответ; без `pypdf` остаётся только путь к файлу.
- `page.route` проверяет HTTP(S)-запросы; WebSocket-соединения
  фильтруются `route_web_socket`, если версия Playwright это
  поддерживает; иначе остаётся сетевая проверка домена.
- Сеть и сторонние сайты могут быть недоступны; таймаут вернёт ошибку.

## Сценарий из JSON

```json
{
  "url": "https://example.com/login",
  "wait": "#form",
  "actions": [
    {"type": "fill", "selector": "#user", "text": "user"},
    {"type": "fill", "selector": "#pass", "text": "secret"},
    {"type": "click", "selector": "#submit"},
    {"type": "wait_url", "url": "/account"},
    {"type": "download", "selector": "a.report"}
  ]
}
```

```powershell
python -m tools.browser_scenario login.json --save result.json
```

Сценарий повторяется целиком; результат можно сохранить и сравнить.
Пароли в JSON не редактируются автоматически — храните файл вне git.
- Браузерные файлы не входят в git и не ставятся автоматически —
  установка отдельная и тяжёлая.
