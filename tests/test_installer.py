import os
import subprocess
from pathlib import Path


def test_installer_uses_expected_uv_package(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    log = tmp_path / "uv.log"
    uv = fake_bin / "uv"
    uv.write_text(
        """#!/bin/sh
if [ "$1" = "tool" ] && [ "$2" = "dir" ]; then
    printf '%s\n' "$FAKE_BIN"
    exit 0
fi
printf '%s\n' "$*" >> "$UV_LOG"
"""
    )
    uv.chmod(0o755)
    project = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.update(
        PATH=f"{fake_bin}:{env['PATH']}",
        FAKE_BIN=str(fake_bin),
        UV_LOG=str(log),
    )

    result = subprocess.run(
        ["sh", str(project / "install.sh")],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert log.read_text().strip() == "tool install --upgrade localmind-graphrag"
    assert "LocalMind is installed." in result.stdout
