"""Shared test isolation.

The checks now resolve manager binaries through `DEVENV_STATE` / `DEVENV_ROOT` and
the toolchain venv, so an ambient devenv shell (which sets exactly those) would
otherwise leak into assertions and make results depend on where the suite is run.
Every test starts from a clean slate and opts back into what it needs.
"""

from __future__ import annotations

import pytest

_AMBIENT = (
    "REPOMAN_MANAGERS",
    "REPOMAN_SKILLS_DIR",
    "REPOMAN_TOOLCHAIN_VENV",
    "REPOMAN_TOOLCHAIN_PYTHON",
    "REPOMAN_LOCK",
    "REPOMAN_ROOT",
    "REPOMAN_SUB_TIMEOUT",
    "REPOMAN_PROVISIONED_DOC",
    "DEVENV_ROOT",
    "DEVENV_STATE",
    "XDG_DATA_HOME",
    "UV_FIND_LINKS",
    "VIRTUAL_ENV",
)


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch, tmp_path):
    for name in _AMBIENT:
        monkeypatch.delenv(name, raising=False)
    # Point the toolchain at a path that cannot exist. `manager_binary()` resolves an
    # absolute path under the toolchain venv, so a test that forgets to stand up a fake
    # one would otherwise read — and `run_sub` would EXECUTE — the real machine
    # toolchain in ~/.local/share/repoman/venv.
    monkeypatch.setenv("REPOMAN_TOOLCHAIN_VENV", str(tmp_path / "no-such-toolchain"))
