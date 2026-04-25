"""In-Memory-Log-Puffer: hält die letzten N Crawler-Logzeilen vor."""

import logging
from collections import deque

_buffer: deque = deque(maxlen=200)


class _BufferHandler(logging.Handler):
    def emit(self, record: logging.LogRecord):
        try:
            _buffer.append(self.format(record))
        except Exception:
            pass


def get_lines() -> list:
    return list(_buffer)


def clear():
    _buffer.clear()


# Handler-Instanz – wird in create_app() registriert
handler = _BufferHandler()
handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    datefmt="%H:%M:%S",
))
