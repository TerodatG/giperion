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
        "terminal/ui/agent/approval.py",
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
    (
        "где проверяются подтверждения записи файлов",
        "terminal/ui/agent/approval.py",
    ),
    (
        "как работает откат изменений агента",
        "terminal/core/agent/rollback.py",
    ),
    (
        "настройка MCP серверов",
        "terminal/core/agent/mcp.py",
    ),
    (
        "где включается песочница AppContainer",
        "tools/setup_plugin_container.py",
    ),
    (
        "как считается расход токенов",
        "terminal/core/agent/budget.py",
    ),
    (
        "где описан стенд оценки агента",
        "tools/eval_agent.py",
    ),
    (
        "как работает сессия браузера",
        "terminal/core/agent/browser_session.py",
    ),
    (
        "где проверяется белый список команд",
        "terminal/core/agent/commands.py",
    ),
    (
        "модуль vector_store и sqlite для векторов",
        "terminal/core/agent/vector_store.py",
    ),
    (
        "build_portable сборка переносимого архива",
        "tools/build_portable.py",
    ),
    (
        "подпись плагина hmac",
        "tools/plugin_sign.py",
    ),
    (
        "установка плагина из папки",
        "tools/plugin_install.py",
    ),
    (
        "due задачи расписание JSON",
        "terminal/core/schedule.py",
    ),
    (
        "сравнение моделей по истории",
        "tools/eval_compare.py",
    ),
    (
        "журнал прогонов агента",
        "terminal/core/agent/runs.py",
    ),
    (
        "вебхук о завершении задачи",
        "terminal/core/agent/notify.py",
    ),
    (
        "граф зависимостей задач",
        "tools/agent_dag.py",
    ),
    (
        "проверка секретов в файлах",
        "tools/scan_secrets.py",
    ),
    (
        "очередь задач агента",
        "terminal/core/agent/queue.py",
    ),
    (
        "каталог плагинов",
        "tools/plugin_catalog.py",
    ),
    (
        "профиль cookies браузера",
        "terminal/core/agent/browser_profile.py",
    ),
    (
        "вкладки браузера",
        "terminal/core/agent/browser_tabs.py",
    ),
    (
        "MCP промпты",
        "terminal/core/agent/mcp_base.py",
    ),
    (
        "квоты MCP",
        "terminal/core/agent/mcp_policy.py",
    ),
    (
        "резервная копия данных",
        "tools/backup_data.py",
    ),
    (
        "browser_page обрезка текста страницы",
        "terminal/core/agent/browser_page.py",
    ),
    (
        "browser_fields поля действий",
        "terminal/core/agent/browser_fields.py",
    ),
    (
        "browser_tabs переключение вкладок",
        "terminal/core/agent/browser_tabs.py",
    ),
    (
        "queue приоритет очереди задач",
        "terminal/core/agent/queue.py",
    ),
    (
        "agent_nightly ночной отчёт",
        "tools/agent_nightly.py",
    ),
    (
        "plugins отзыв разрешений плагина",
        "terminal/core/agent/plugins.py",
    ),
    (
        "agent_issue gitlab token",
        "tools/agent_issue.py",
    ),
    (
        "onboarding флаг первого запуска",
        "terminal/core/agent/onboarding.py",
    ),
    (
        "plan parse статус пункта",
        "terminal/core/agent/plan.py",
    ),
    (
        "loop_audit цель вызова",
        "terminal/core/agent/loop_audit.py",
    ),
    (
        "errors retry ask stop",
        "terminal/core/agent/errors.py",
    ),
)
