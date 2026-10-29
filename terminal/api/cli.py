# Giperion/terminal/api/cli.py                                         v001
# Командная строка API: serve, version, tools, runs, run.

import argparse
import json
import sys

from terminal.api import api_config as config
from terminal.api import server
from terminal.api.client import Client, ClientError

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _client(args) -> Client:
    """Клиент с адресом и токеном из аргументов или окружения."""

    return Client(
        base_url=args.url,
        token=args.token or config.api_token(),
        timeout=args.timeout,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="giperion-api",
        description="HTTP-API терминала Giperion.",
    )
    parser.add_argument("--url", default="", help="адрес API")
    parser.add_argument("--token", default="", help="токен доступа")
    parser.add_argument("--timeout", type=float, default=600.0)

    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="запустить сервер")
    serve.add_argument("--host", default="")
    serve.add_argument("--port", type=int, default=None)

    sub.add_parser("version", help="версия API")
    sub.add_parser("tools", help="список инструментов")

    runs = sub.add_parser("runs", help="последние прогоны")
    runs.add_argument("--limit", type=int, default=10)

    run = sub.add_parser("run", help="выполнить задачу")
    run.add_argument("task")
    run.add_argument("--project", default=".")
    run.add_argument("--steps", type=int, default=config.DEFAULT_STEPS)
    run.add_argument("--policy", default="read")

    args = parser.parse_args()

    if args.command == "serve":
        return server.serve(args.host, args.port)

    client = _client(args)

    try:
        if args.command == "version":
            print(json.dumps(client.version(), ensure_ascii=False))
        elif args.command == "tools":
            print("\n".join(client.tools()))
        elif args.command == "runs":
            for item in client.runs(args.limit):
                print(
                    f"{item.get('at', '')} · {item.get('task', '')[:60]}"
                )
        elif args.command == "run":
            result = client.run(
                args.task,
                project=args.project,
                steps=args.steps,
                policy=args.policy,
            )
            print(result.get("answer") or "")
            print(
                f"шагов: {len(result.get('steps') or [])} · "
                f"ok: {result.get('ok')}",
                file=sys.stderr,
            )

            if result.get("error"):
                print("ошибка:", result["error"], file=sys.stderr)

                return 1
    except ClientError as error:
        print("ошибка:", error, file=sys.stderr)

        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
