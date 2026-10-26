# Giperion/tools/retrieval_cases.py                                   v001
# Запросы для проверки смыслового поиска и ожидаемые файлы.
# Последнее изменение: первый набор из семи запросов по проекту.

CASES = (
    (
        "изоляция плагинов в отдельном процессе",
        "terminal/core/agent/plugin_runner.py",
    ),
    (
        "mcp allowlist domains for url arguments",
        "terminal/core/agent/mcp_policy.py",
    ),
    (
        "бюджет контекста из окна модели",
        "terminal/core/agent/context_budget.py",
    ),
    (
        "защита от чтения секретов и ключей",
        "terminal/core/agent/redact.py",
    ),
    (
        "смысловой поиск и эмбеддинги",
        "terminal/core/agent/semantic.py",
    ),
    (
        "подтверждения записи файлов",
        "terminal/core/agent/loop_tools.py",
    ),
    (
        "откат изменений агента после ошибки",
        "terminal/core/agent/rollback.py",
    ),
    (
        "где хранятся резервные копии файлов",
        "terminal/core/agent/tools_write.py",
    ),
    (
        "как ограничить сеть для плагинов",
        "terminal/core/agent/plugin_runner.py",
    ),
    (
        "защита от SSRF при чтении страниц",
        "terminal/core/agent/web.py",
    ),
    (
        "настройка модели эмбеддингов",
        "terminal/core/agent/embeddings.py",
    ),
    (
        "как работает наблюдатель за файлами",
        "terminal/core/agent/watch.py",
    ),
)
