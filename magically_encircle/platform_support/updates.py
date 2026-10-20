"""Version feed checker (same idea as the macOS app)."""

from __future__ import annotations

import json
import logging
import re
import threading
import urllib.request
from typing import Any

from PySide6.QtCore import QObject, Signal

from .. import __version__

log = logging.getLogger(__name__)

FEED_URL = (
    "https://raw.githubusercontent.com/Si-jiyuan/magicallyEncircle/main/version-win.json"
)


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = [int(item) for item in re.findall(r"\d+", value)]
    return tuple(parts) if parts else (0,)


class UpdateChecker(QObject):
    result_ready = Signal(str, object)  # status: "update" | "latest" | "error"; payload

    def check(self, manual: bool = False) -> None:
        threading.Thread(target=self._worker, args=(manual,), name="UpdateCheck", daemon=True).start()

    def _worker(self, manual: bool) -> None:
        request = urllib.request.Request(
            f"{FEED_URL}?t={int(__import__('time').time())}",
            headers={"User-Agent": "magicallyEncircle-Windows"},
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                payload: dict[str, Any] = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            log.info("Update check failed: %s", exc)
            if manual:
                self.result_ready.emit("error", None)
            return
        remote = str(payload.get("version") or "0")
        if _version_tuple(remote) > _version_tuple(__version__):
            self.result_ready.emit("update", payload)
        elif manual:
            self.result_ready.emit("latest", payload)
