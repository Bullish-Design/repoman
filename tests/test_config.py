from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from repoman.config import AccountConfig, GlobalConfig, RepoConfig, RepomanConfig


def test_repo_config_expands_local_dir() -> None:
    config = RepoConfig(name="repo", local_dir="~/example")
    assert config.local_dir == Path("~/example").expanduser().resolve()


def test_repo_config_rejects_invalid_names() -> None:
    for name in ("repo@name", "repo name", "repo/name", ""):
        with pytest.raises(ValidationError):
            RepoConfig(name=name)


def test_repo_config_accepts_valid_names() -> None:
    for name in ("my-repo", "my_repo", "my.repo", "MyRepo123"):
        RepoConfig(name=name)


def test_repo_config_validates_remote_name() -> None:
    config = RepoConfig(name="local", remote_name="Remote-Repo")
    assert config.remote_name == "Remote-Repo"
    with pytest.raises(ValidationError):
        RepoConfig(name="local", remote_name="bad name")


def test_account_config_normalizes_dict_repos() -> None:
    account = AccountConfig(name="example", repos=[{"name": "repo"}])
    assert isinstance(account.repos[0], RepoConfig)


def test_account_requires_repos() -> None:
    with pytest.raises(ValidationError):
        AccountConfig(name="example", repos=[])


def test_global_config_expands_base_dir() -> None:
    global_config = GlobalConfig(base_dir="~/code")
    assert global_config.base_dir == Path("~/code").expanduser().resolve()


def test_global_config_max_concurrent_bounds() -> None:
    for invalid_value in (0, 51):
        with pytest.raises(ValidationError):
            GlobalConfig(max_concurrent=invalid_value)


def test_global_config_timeout_bounds() -> None:
    for invalid_value in (29, 3601):
        with pytest.raises(ValidationError):
            GlobalConfig(timeout=invalid_value)


def test_duplicate_account_names_are_rejected() -> None:
    with pytest.raises(ValidationError):
        RepomanConfig(
            **{
                "accounts": [
                    {"name": "acct", "repos": ["repo1"]},
                    {"name": "acct", "repos": ["repo2"]},
                ]
            }
        )


def test_duplicate_repo_names_within_account_are_rejected() -> None:
    with pytest.raises(ValidationError):
        RepomanConfig(
            **{
                "accounts": [
                    {"name": "acct", "repos": ["repo1", {"name": "repo1"}]},
                ]
            }
        )


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
                        {"name": "local-name", "remote_name": "Remote-Name"},
                    ],
                }
            ],
        }
    )

    base_dir = Path("~/work").expanduser().resolve()
    assert repoman.get_repo_path("acct", "simple") == base_dir / "acct" / "simple"
    custom = RepoConfig(name="custom", local_dir="~/override")
    assert repoman.get_repo_path("acct", custom) == Path("~/override").expanduser().resolve()
    remote = RepoConfig(name="local-name", remote_name="Remote-Name")
    assert repoman.get_repo_path("acct", remote) == base_dir / "acct" / "local-name"
