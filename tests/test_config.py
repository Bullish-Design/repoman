from __future__ import annotations

from pathlib import Path

import pytest

from repoman.config import AccountConfig, GlobalConfig, RepoConfig, RepomanConfig


def test_repo_config_expands_local_dir() -> None:
    config = RepoConfig(name="repo", local_dir="~/example")
    assert config.local_dir == Path("~/example").expanduser().resolve()


def test_account_config_normalizes_dict_repos() -> None:
    account = AccountConfig(name="example", repos=[{"name": "repo"}])
    assert isinstance(account.repos[0], RepoConfig)


def test_account_requires_repos() -> None:
    with pytest.raises(ValueError):
        AccountConfig(name="example", repos=[])


def test_global_config_expands_base_dir() -> None:
    global_config = GlobalConfig(base_dir="~/code")
    assert global_config.base_dir == Path("~/code").expanduser().resolve()


def test_repo_path_resolution_order() -> None:
    repoman = RepomanConfig(
        **{
            "global": {"base_dir": "~/code"},
            "accounts": [
                {
                    "name": "acct",
                    "base_dir": "~/work",
                    "repos": [
                        "simple",
                        {"name": "custom", "local_dir": "~/override"},
                    ],
                }
            ],
        }
    )

    base_dir = Path("~/work").expanduser().resolve()
    assert repoman.get_repo_path("acct", "simple") == base_dir / "acct" / "simple"
    custom = RepoConfig(name="custom", local_dir="~/override")
    assert repoman.get_repo_path("acct", custom) == Path("~/override").expanduser().resolve()
