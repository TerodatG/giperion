# Giperion/tests/fixtures/fake_lsp.py                                 v001
# Заглушка языкового сервера: отвечает по протоколу LSP для тестов.
#
# Запуск: python tests/fixtures/fake_lsp.py

import json
import sys


def read_message():
    """Читает одно сообщение LSP из stdin."""

    length = None

    while True:
        line = sys.stdin.buffer.readline()

        if not line:
            return None

        text = line.decode("ascii", errors="replace").strip()

        if not text:
            break

        if text.lower().startswith("content-length:"):
            length = int(text.split(":", 1)[1].strip())

    if not length:
        return None

    body = sys.stdin.buffer.read(length)

    return json.loads(body.decode("utf-8"))


def write_message(payload):
    """Пишет сообщение LSP в stdout."""

    body = json.dumps(payload).encode("utf-8")
    sys.stdout.buffer.write(
        f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body
    )
    sys.stdout.buffer.flush()


def diagnostics_for(uri):
    """Две проблемы: ошибка и предупреждение."""

    return {
        "jsonrpc": "2.0",
        "method": "textDocument/publishDiagnostics",
        "params": {
            "uri": uri,
            "diagnostics": [
                {
                    "range": {
                        "start": {"line": 2, "character": 4},
                        "end": {"line": 2, "character": 9},
                    },
                    "severity": 1,
                    "code": "E001",
                    "message": "неизвестное имя",
                },
                {
                    "range": {
                        "start": {"line": 6, "character": 0},
                        "end": {"line": 6, "character": 3},
                    },
                    "severity": 2,
                    "message": "не используется",
                },
            ],
        },
    }


def location(uri, line, character):
    """Location для определений и ссылок."""

    return {
        "uri": uri,
        "range": {
            "start": {"line": line, "character": character},
            "end": {"line": line, "character": character + 4},
        },
    }


def main():
    """Обслуживает запросы до exit."""

    while True:
        message = read_message()

        if message is None:
            return

        method = message.get("method")
        params = message.get("params") or {}
        request_id = message.get("id")

        if method == "initialize":
            write_message(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"capabilities": {}},
                }
            )
        elif method == "textDocument/didOpen":
            uri = (params.get("textDocument") or {}).get("uri", "")
            write_message(diagnostics_for(uri))
        elif method == "textDocument/definition":
            uri = (params.get("textDocument") or {}).get("uri", "")
            write_message(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": location(uri, 4, 2),
                }
            )
        elif method == "textDocument/references":
            uri = (params.get("textDocument") or {}).get("uri", "")
            write_message(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": [
                        location(uri, 4, 2),
                        location(uri, 9, 0),
                    ],
                }
            )
        elif method == "textDocument/documentSymbol":
            uri = (params.get("textDocument") or {}).get("uri", "")
            write_message(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": [
                        {
                            "name": "main",
                            "kind": 12,
                            "range": {
                                "start": {"line": 0, "character": 0},
                                "end": {"line": 3, "character": 0},
                            },
                        },
                        {
                            "name": "Helper",
                            "kind": 5,
                            "range": {
                                "start": {"line": 5, "character": 0},
                                "end": {"line": 9, "character": 0},
                            },
                        },
                    ],
                }
            )
        elif method == "textDocument/hover":
            write_message(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "contents": {
                            "kind": "markdown",
                            "value": "def main() -> None",
                        }
                    },
                }
            )
        elif method == "shutdown":
            write_message(
                {"jsonrpc": "2.0", "id": request_id, "result": None}
            )
        elif method == "exit":
            return
        elif request_id is not None:
            write_message(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": None,
                }
            )


if __name__ == "__main__":
    main()
