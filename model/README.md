# GiperionModel

Самостоятельный проект модели **Giperion**: намерения, знания, обучение и
нейросетевой инференс. Приложение «Терминал» подключает его как пакет
`giperion_model`.

```
model/
  giperion_model/
    api.py              точка входа: intent → neural
    config.py           пути (env GIPERION_*)
    identity_matrix.py
    personality_catalog.py
    neural_engine.py    загрузка чекпоинтов и ответ
    language/           намерения и обучение фразам
    training/           датасет, токенизаторы, тренеры
    _shared/            локальная копия json_store/text_tools/action_log
  tests/                чистые тесты модели
  pyproject.toml
```

## Установка

Из корня приложения:

```powershell
python -m pip install -e model
```

Или из этой папки:

```powershell
python -m pip install -e .
```

## Пути

`config.py` берёт каталоги из окружения, по умолчанию — текущая папка:

| Переменная | По умолчанию |
|---|---|
| `GIPERION_HOME` | текущая папка |
| `GIPERION_DATA_DIR` | `$GIPERION_HOME/data` |
| `GIPERION_MODELS_DIR` | `$GIPERION_HOME/models` |
| `GIPERION_LOGS_DIR` | `$GIPERION_HOME/logs` |

Приложение при старте выставляет эти переменные по своим путям, поэтому
данные и чекпоинты остаются общими.

## Тесты

```powershell
python -m pytest model/tests
```

Чистые тесты модели не импортируют `terminal` и приложение.

## Граница

- `giperion_model` **не импортирует** `terminal` и не знает про агента.
- `shared` и `config` приложения не используются: пути — в
  `giperion_model.config`, три общих модуля скопированы в `_shared`.
- Приложение импортирует только публичный пакет `giperion_model`.

## Отдельный репозиторий

Папка самодостаточна: у неё свой `pyproject.toml`, тесты и `.gitignore`.
Чтобы вынести в отдельный репозиторий, достаточно скопировать `model/`
и выполнить `git init`; приложению останется `pip install -e <путь>`.
