from __future__ import annotations

from pathlib import Path

import pytest

from repoman.config import RepomanConfig
from repoman.manager import ProgressCallback, ProgressLevel, RepoManager


class FakeGitHubClient:
    def __init__(self) -> None:
        self.cloned: list[tuple[str, str, Path]] = []

    def repo_exists(self, path: Path) -> bool:
        return False

    def has_uncommitted_changes(self, path: Path) -> bool:
        return False

    async def clone_repo(self, account: str, repo: str, dest: Path) -> None:
        if repo == "bad":
            raise RuntimeError("clone failed")
        self.cloned.append((account, repo, dest))

    async def update_repo(self, path: Path) -> tuple[bool, str]:
        return True, "updated"


def _config() -> RepomanConfig:
    return RepomanConfig(
        **{
            "global": {"base_dir": "~/code", "max_concurrent": 2},
            "accounts": [
                {"name": "acct", "repos": ["good", "bad"]},
            ],
        }
    )


@pytest.mark.asyncio
async def test_sync_all_reports_results() -> None:
    progress_messages: list[str] = []

    def _progress(message: str, level: ProgressLevel = "info") -> None:
        progress_messages.append(f"{level}:{message}")

    github = FakeGitHubClient()
    manager = RepoManager(_config(), github_client=github)
    results = await manager.sync_all(progress=_progress)

    statuses = {result.repo: result.status for result in results}
    assert statuses["good"] == "cloned"
    assert statuses["bad"] == "error"
    assert any("Syncing acct/good" in message for message in progress_messages)


def test_manager_passes_timeout_to_github_client(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, int] = {}

    class DummyGitHubClient:
        def __init__(self, *, timeout: int, **_: object) -> None:
            captured["timeout"] = timeout

    monkeypatch.setattr("repoman.manager.GitHubClient", DummyGitHubClient)
    config = RepomanConfig(
        **{
            "global": {"base_dir": "~/code", "max_concurrent": 2, "timeout": 123},
            "accounts": [],
        }
    )

    RepoManager(config)

    assert captured["timeout"] == 123


@pytest.mark.asyncio
async def test_progress_callback_for_updates() -> None:
    progress_messages: list[str] = []

    def _progress(message: str, level: ProgressLevel = "info") -> None:
        progress_messages.append(f"{level}:{message}")

    class UpdatingGitHubClient:
        def repo_exists(self, path: Path) -> bool:
            return True

        def has_uncommitted_changes(self, path: Path) -> bool:
            return False

        async def update_repo(self, path: Path) -> tuple[bool, str]:
            return True, "updated"

        async def clone_repo(self, account: str, repo: str, dest: Path) -> None:
            raise RuntimeError("clone should not be called")

    config = RepomanConfig(
        **{
            "global": {"base_dir": "~/code", "max_concurrent": 2},
            "accounts": [{"name": "acct", "repos": ["updated"]}],
        }
    )
    manager = RepoManager(config, github_client=UpdatingGitHubClient())

    result = await manager.sync_repo("acct", "updated", progress=_progress)

    assert result.status == "updated"
    assert any(message.startswith("info:Updating acct/updated") for message in progress_messages)
    assert any(message.startswith("info:Updated acct/updated") for message in progress_messages)


@pytest.mark.asyncio
async def test_sync_repo_skips_uncommitted_changes() -> None:
    progress_messages: list[str] = []

    def _progress(message: str, level: ProgressLevel = "info") -> None:
        progress_messages.append(f"{level}:{message}")

    class DirtyGitHubClient:
        def __init__(self) -> None:
            self.update_called = False

        def repo_exists(self, path: Path) -> bool:
            return True

        def has_uncommitted_changes(self, path: Path) -> bool:
            return True

        async def update_repo(self, path: Path) -> tuple[bool, str]:
            self.update_called = True
            return True, "updated"

        async def clone_repo(self, account: str, repo: str, dest: Path) -> None:
            raise RuntimeError("clone should not be called")

    github = DirtyGitHubClient()
    config = RepomanConfig(
        **{
            "global": {"base_dir": "~/code", "max_concurrent": 2},
            "accounts": [{"name": "acct", "repos": ["dirty"]}],
        }
    )
    manager = RepoManager(config, github_client=github)
    result = await manager.sync_repo("acct", "dirty", progress=_progress)

    assert result.status == "skipped"
    assert "uncommitted changes" in result.message
    assert github.update_called is False
    assert any(message.startswith("warning:Skipped acct/dirty") for message in progress_messages)


@pytest.mark.asyncio
async def test_progress_callback_for_errors() -> None:
    progress_messages: list[str] = []

    def _progress(message: str, level: ProgressLevel = "info") -> None:
        progress_messages.append(f"{level}:{message}")

    class FailingGitHubClient:
        def repo_exists(self, path: Path) -> bool:
            return False

        def has_uncommitted_changes(self, path: Path) -> bool:
            return False

        async def update_repo(self, path: Path) -> tuple[bool, str]:
            return True, "updated"

        async def clone_repo(self, account: str, repo: str, dest: Path) -> None:
            raise RuntimeError("clone failed")

    config = RepomanConfig(
        **{
            "global": {"base_dir": "~/code", "max_concurrent": 2},
            "accounts": [{"name": "acct", "repos": ["bad"]}],
        }
    )
    manager = RepoManager(config, github_client=FailingGitHubClient())

    result = await manager.sync_repo("acct", "bad", progress=_progress)

    assert result.status == "error"
    assert any(
        message.startswith("error:Failed acct/bad: clone failed") for message in progress_messages
    )


def test_progress_callback_type_compatibility() -> None:
    def _progress(message: str, level: ProgressLevel = "info") -> None:
        assert message
        assert level in ("info", "success", "warning", "error")

    callback: ProgressCallback = _progress
    assert callable(callback)
