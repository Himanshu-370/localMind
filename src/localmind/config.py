"""LocalMind settings persisted in the user's configuration directory."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .paths import default_paths


@dataclass
class Config:
    roots: list[str] = field(default_factory=list)
    llm_model: str = "qwen3:4b"
    embed_model: str = "nomic-embed-text"
    ollama_host: str = "http://127.0.0.1:11434"
    max_file_mb: int = 5
    graph_mode: str = "hybrid"
    stale: bool = False
    blocked: bool = False

    def save(self, path: Path | None = None) -> None:
        path = path or default_paths().config
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        try:
            tmp.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
            try:
                tmp.chmod(0o600)
            except OSError:
                pass
            tmp.replace(path)
        finally:
            if tmp.exists():
                tmp.unlink()

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        path = path or default_paths().config
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)


def is_loopback(url: str) -> bool:
    """All inference endpoints must remain on this computer."""
    from urllib.parse import urlparse

    return (urlparse(url).hostname or "") in ("127.0.0.1", "localhost", "::1")
