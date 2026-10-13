from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

DEFAULT_BASE_URL = "https://ntfy.sh"
DEFAULT_TIMEOUT = 5


@dataclass
class Notifier:
    topic: str
    base_url: str = DEFAULT_BASE_URL
    token: str | None = None
    timeout: int = DEFAULT_TIMEOUT

    def _headers(self, title: str, priority: str, tags: str) -> dict[str, str]:
        headers = {"Title": title, "Priority": priority, "Tags": tags}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def send(self, message: str, title: str = "frame", priority: str = "default", tags: str = "bell") -> bool:
        url = f"{self.base_url.rstrip('/')}/{self.topic}"
        request = urllib.request.Request(
            url,
            data=message.encode("utf-8"),
            headers=self._headers(title, priority, tags),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return 200 <= response.status < 300
        except (urllib.error.URLError, OSError, ValueError):
            return False

    def test(self) -> bool:
        return self.send("frame notifier probe", title="frame test", priority="min")


class LocalNotifier:
    """Writes to a file instead of a network. The default in every test and dry run."""

    def __init__(self, path: str) -> None:
        self.path = path

    def send(self, message: str, title: str = "frame", priority: str = "default", tags: str = "bell") -> bool:
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps({"title": title, "body": message, "priority": priority}, ensure_ascii=False) + "\n")
        return True

    def test(self) -> bool:
        return self.send("frame notifier probe", title="frame test", priority="min")
