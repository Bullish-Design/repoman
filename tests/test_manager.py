from __future__ import annotations

from pathlib import Path

import pytest

from repoman.config import RepomanConfig
from repoman.manager import RepoManager


class FakeGitHubClient:
    def __init__(self) -> None:
        self.cloned: list[tuple[str, str, Path]] = []

    def repo_exists(self, path: Path) -> bool:
        return False

    def clone_repo(self, account: str, repo: str, dest: Path) -> None:
        if repo == "bad":
            raise RuntimeError("clone failed")
        self.cloned.append((account, repo, dest))

    def update_repo(self, path: Path) -> tuple[bool, str]:
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

    def _progress(message: str, level: str = "info") -> None:
        progress_messages.append(f"{level}:{message}")

    github = FakeGitHubClient()
    manager = RepoManager(_config(), github_client=github)
    results = await manager.sync_all(progress=_progress)

    statuses = {result.repo: result.status for result in results}
    assert statuses["good"] == "cloned"
    assert statuses["bad"] == "error"
    assert any("Syncing acct/good" in message for message in progress_messages)
