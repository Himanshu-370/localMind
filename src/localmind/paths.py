"""Platform-appropriate, user-owned paths for mutable LocalMind data."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_cache_path, user_config_path, user_data_path


@dataclass(frozen=True)
class AppPaths:
    config_dir: Path
    data_dir: Path
    cache_dir: Path

    @property
    def config(self) -> Path:
        return self.config_dir / "config.json"

    @property
    def storage(self) -> Path:
        return self.data_dir / "storage"

    @property
    def vault(self) -> Path:
        return self.data_dir / "vault"

    @property
    def excluded_dirs(self) -> tuple[Path, ...]:
        return (self.config_dir, self.data_dir, self.cache_dir)

    def ensure_base_dirs(self) -> None:
        for directory in {self.config_dir, self.data_dir, self.cache_dir}:
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            try:
                directory.chmod(0o700)
            except OSError:
                pass


def default_paths() -> AppPaths:
    """Resolve paths once per call so tests and support tools can override them."""
    override = os.environ.get("LOCALMIND_DATA_DIR")
    if override:
        root = Path(override).expanduser().resolve()
        return AppPaths(root, root, root / "cache")
    app_name = "LocalMind" if sys.platform in {"darwin", "win32"} else "localmind"
    return AppPaths(
        Path(user_config_path(app_name, appauthor=False)),
        Path(user_data_path(app_name, appauthor=False)),
        Path(user_cache_path(app_name, appauthor=False)),
    )
