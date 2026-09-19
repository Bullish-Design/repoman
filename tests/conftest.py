"""Shared test isolation.

The checks now resolve manager binaries through `DEVENV_STATE` / `DEVENV_ROOT` and
the Vendomat store, so an ambient devenv shell (which sets exactly those) would
otherwise leak into assertions and make results depend on where the suite is run.
Every test starts from a clean slate and opts back into what it needs.
"""

from __future__ import annotations

import pytest

_AMBIENT = (
    "REPOMAN_MANAGERS",
    "REPOMAN_SKILLS_DIR",
    "REPOMAN_TOOLCHAIN_BIN",
    "REPOMAN_TOOLCHAIN_MANIFEST",
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
    # Point the store at a path that cannot exist. A test that forgets to stand up a
    # fake one must never execute a real host toolchain.
    monkeypatch.setenv("REPOMAN_TOOLCHAIN_BIN", str(tmp_path / "no-such-toolchain"))
