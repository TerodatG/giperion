# Giperion/tools/mcp_status.py                                        v001
# Статус MCP-серверов: инструменты, ресурсы и ошибки.
# Последнее изменение: первый вариант — таблица и --json.

import argparse
import json
import sys

from terminal.core.agent import mcp, mcp_status


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Проверить MCP-серверы из data/agent_mcp.json.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    servers = mcp.load_servers()

    if not servers:
        print("MCP-серверы не настроены: data/agent_mcp.json.")
        return 0

    rows = mcp_status.probe_all()

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for row in rows:
            if row["ok"]:
                print(
                    f"OK · {row['name']}: "
                    f"инструментов {row['tools']}, "
                    f"ресурсов {row['resources']}"
                )
            else:
                print(f"ОШИБКА · {row['name']}: {row['error']}")

    return 0 if all(row["ok"] for row in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
