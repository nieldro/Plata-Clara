"""Limitador de intentos en memoria (ventana deslizante).

Sirve para frenar la adivinación de contraseñas y el registro masivo de cuentas. Vive en la memoria del proceso:
con una sola instancia de la API (el caso de este proyecto) es suficiente; si algún día hay varias réplicas,
habría que moverlo a Redis.
"""
import time
from collections import deque
from typing import Callable

MAX_KEYS = 10_000  # tope de claves guardadas: evita que alguien llene la memoria con correos inventados


class SlidingWindowLimiter:
    def __init__(self, max_events: int, window_seconds: int, clock: Callable[[], float] = time.monotonic):
        self.max_events = max_events
        self.window = window_seconds
        self.clock = clock
        self._events: dict[str, deque[float]] = {}

    def _prune(self, key: str) -> deque[float]:
        q = self._events.setdefault(key, deque())
        cutoff = self.clock() - self.window
        while q and q[0] <= cutoff:
            q.popleft()
        if not q:
            self._events.pop(key, None)
        return q

    def retry_after(self, key: str) -> int:
        """Segundos que faltan para poder intentar de nuevo (0 si no está bloqueado)."""
        q = self._prune(key)
        if len(q) < self.max_events:
            return 0
        return max(1, int(q[0] + self.window - self.clock()) + 1)

    def record(self, key: str) -> None:
        if len(self._events) >= MAX_KEYS:
            for k in list(self._events):
                self._prune(k)
            if len(self._events) >= MAX_KEYS:  # sigue lleno de claves vigentes: descarta las más viejas
                for k in list(self._events)[: MAX_KEYS // 10]:
                    self._events.pop(k, None)
        self._events.setdefault(key, deque()).append(self.clock())

    def reset(self, key: str) -> None:
        self._events.pop(key, None)

    def clear(self) -> None:
        self._events.clear()


def _build():
    from ..config import settings

    window = settings.login_window_seconds
    return (
        SlidingWindowLimiter(settings.login_max_failures, window),         # fallos por IP + correo
        SlidingWindowLimiter(settings.login_ip_max_failures, window),      # fallos por IP, cualquier correo
        SlidingWindowLimiter(settings.register_max_per_hour, 3600),        # registros por IP
        SlidingWindowLimiter(settings.heavy_max_per_minute, 60),           # operaciones pesadas por usuario
    )


login_limiter, login_ip_limiter, register_limiter, heavy_limiter = _build()


def clear_all() -> None:
    for limiter in (login_limiter, login_ip_limiter, register_limiter, heavy_limiter):
        limiter.clear()
