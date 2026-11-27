import json

from localmind.config import Config
from localmind.paths import AppPaths, default_paths


def test_config_round_trip_and_unknown_fields(tmp_path):
    path = tmp_path / "nested" / "config.json"
    Config(roots=["/notes"], stale=True).save(path)
    data = json.loads(path.read_text())
    data["future_setting"] = True
    path.write_text(json.dumps(data))

    loaded = Config.load(path)
    assert loaded.roots == ["/notes"]
    assert loaded.stale is True


def test_invalid_config_returns_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{broken")
    assert Config.load(path) == Config()


def test_data_dir_override(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALMIND_DATA_DIR", str(tmp_path / "profile"))
    paths = default_paths()
    assert paths == AppPaths(tmp_path / "profile", tmp_path / "profile", tmp_path / "profile/cache")
    paths.ensure_base_dirs()
    assert paths.data_dir.is_dir() and paths.cache_dir.is_dir()
