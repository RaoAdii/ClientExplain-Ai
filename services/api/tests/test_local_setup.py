"""Exercise setup in a disposable checkout without touching real credentials."""

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("filename", ["configure.py", "setup.ps1"])
def test_fresh_setup_matches_local_services_and_preserves_existing_files(tmp_path, filename):
    source = Path(__file__).resolve().parents[3] / "scripts" / filename
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (tmp_path / "apps/web").mkdir(parents=True)
    script = scripts / filename
    script.write_bytes(source.read_bytes())
    command = (
        [sys.executable, str(script)]
        if filename.endswith(".py")
        else ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)]
    )
    subprocess.run(command, check=True, capture_output=True)
    backend = (tmp_path / ".env").read_text()
    frontend = (tmp_path / "apps/web/.env.local").read_text()
    assert "APP_ENV=development\n" in frontend
    assert "@127.0.0.1:5433/clientexplain" in backend
    subprocess.run(command, check=True, capture_output=True)
    assert (tmp_path / ".env").read_text() == backend
    assert (tmp_path / "apps/web/.env.local").read_text() == frontend
