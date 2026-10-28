# Giperion/terminal/api/__init__.py                                    v001
# HTTP-API терминала: запуск задач агента из других программ.

from terminal.api.client import Client, ClientError

__all__ = ["Client", "ClientError"]
