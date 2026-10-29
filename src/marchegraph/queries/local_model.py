"""Client du modèle local Ollama, joignable uniquement en loopback (AD-3, AD-4)."""
from __future__ import annotations

import json
import re
import urllib.request
from urllib.parse import urlparse

LOCAL_MODEL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
DEFAULT_MODEL_URL = "http://127.0.0.1:11434"


class LocalModelURLError(ValueError):
    pass


class OllamaClient:
    """Appelable `client(prompt) -> texte`, sans état partagé."""

    def __init__(
        self, model: str, base_url: str = DEFAULT_MODEL_URL, *, timeout: float = 120
    ) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme != "http" or parsed.hostname not in LOCAL_MODEL_HOSTS:
            raise LocalModelURLError(
                "Le modèle doit être local ; l'URL doit utiliser http et "
                "localhost, 127.0.0.1 ou ::1."
            )
        self.model = model
        self.url = base_url.rstrip("/") + "/api/generate"
        self.timeout = timeout

    def __call__(self, prompt: str) -> str:
        body = json.dumps({
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0, "seed": 42, "num_predict": 400},
        }).encode()
        request = urllib.request.Request(
            self.url, data=body, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            data = json.load(response)
        return re.sub(r"<think>.*?</think>", "", data.get("response", ""),
                      flags=re.S).strip()
