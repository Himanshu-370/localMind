import pytest

from localmind import __version__
from localmind.cli import main


def test_paths_uses_override(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("LOCALMIND_DATA_DIR", str(tmp_path))
    assert main(["paths"]) == 0
    output = capsys.readouterr().out
    assert f"Data:    {tmp_path}" in output
    assert f"Vault:   {tmp_path / 'vault'}" in output


def test_version_does_not_launch_gui(capsys):
    with pytest.raises(SystemExit) as result:
        main(["--version"])
    assert result.value.code == 0
    assert capsys.readouterr().out.strip() == f"LocalMind {__version__}"
