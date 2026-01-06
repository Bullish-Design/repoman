# src/repoman/manager.py
"""Repository manager for repoman."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel

from repoman.config import AccountConfig, RepoConfig, RepomanConfig
from repoman.github import GitHubClient


ProgressLevel = Literal["info", "success", "warning", "error"]


class ProgressCallback(Protocol):
    """Protocol for progress reporting.

    Implementations receive progress updates during sync operations.
    """

    def __call__(self, message: str, level: ProgressLevel = "info") -> None:
        """Report progress.

        Args:
            message: Progress message to report
            level: Message severity - "info", "success", "warning", "error"
        """


class SyncResult(BaseModel):
    """Result of a single repository sync operation.

    Attributes:
        account: GitHub account name
        repo: Repository name
        status: Operation result - "cloned", "updated", "up-to-date", "skipped", "error"
        message: Additional information (error message if status is "error")
        path: Local path where repository is located
    """

    account: str
    repo: str
    status: Literal["cloned", "updated", "up-to-date", "skipped", "error"]
    message: str = ""
    path: Path


class RepoManager:
    """Manager for repository operations with concurrent sync support."""

    def __init__(self, config: RepomanConfig, github_client: GitHubClient | None = None) -> None:
        """Initialize repository manager.

        Args:
            config: Repository configuration
            github_client: GitHub client (creates default if None)
        """

        self.config = config
        self.github = github_client or GitHubClient(timeout=self.config.global_config.timeout)
        self._semaphore = asyncio.Semaphore(config.global_config.max_concurrent)

    async def sync_all(self, progress: ProgressCallback | None = None) -> list[SyncResult]:
        """Sync all configured repositories concurrently.

        Creates async tasks for all repositories and executes them concurrently
        with a semaphore limiting active operations.

        Args:
            progress: Optional callback for progress updates

        Returns:
            List of SyncResult objects for all repositories
        """

        tasks: list[asyncio.Task[SyncResult]] = []
        for account in self.config.accounts:
            for repo in account.repos:
                tasks.append(asyncio.create_task(self._sync_single_repo(account, repo, progress)))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        final_results: list[SyncResult] = []
        for result in results:
            if isinstance(result, SyncResult):
                final_results.append(result)
            elif isinstance(result, Exception):
                final_results.append(
                    SyncResult(
                        account="unknown",
                        repo="unknown",
                        status="error",
                        message=str(result),
                        path=Path("."),
                    )
                )
        return final_results

    async def sync_account(self, account_name: str, progress: ProgressCallback | None = None) -> list[SyncResult]:
        """Sync all repositories for specific account concurrently.

        Args:
            account_name: GitHub account name
            progress: Optional callback for progress updates

        Returns:
            List of SyncResult objects

        Raises:
            ValueError: If account not found in configuration
        """

        account = next((item for item in self.config.accounts if item.name == account_name), None)
        if account is None:
            raise ValueError(f"Account {account_name} not found in configuration")
        tasks = [asyncio.create_task(self._sync_single_repo(account, repo, progress)) for repo in account.repos]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        final_results: list[SyncResult] = []
        for result in results:
            if isinstance(result, SyncResult):
                final_results.append(result)
            elif isinstance(result, Exception):
                final_results.append(
                    SyncResult(
                        account=account_name,
                        repo="unknown",
                        status="error",
                        message=str(result),
                        path=Path("."),
                    )
                )
        return final_results

    async def sync_repo(
        self, account_name: str, repo_name: str, progress: ProgressCallback | None = None
    ) -> SyncResult:
        """Sync a specific repository.

        Args:
            account_name: GitHub account name
            repo_name: Repository name
            progress: Optional callback for progress updates

        Returns:
            SyncResult object

        Raises:
            ValueError: If account or repository not found
        """

        account = next((item for item in self.config.accounts if item.name == account_name), None)
        if account is None:
            raise ValueError(f"Account {account_name} not found in configuration")
        repo = next(
            (
                item
                for item in account.repos
                if (item.name if isinstance(item, RepoConfig) else item) == repo_name
            ),
            None,
        )
        if repo is None:
            raise ValueError(f"Repository {repo_name} not found in account {account_name}")
        return await self._sync_single_repo(account, repo, progress)

    async def _sync_single_repo(
        self, account: AccountConfig, repo: str | RepoConfig, progress: ProgressCallback | None = None
    ) -> SyncResult:
        """Internal: Sync a single repository.

        This is the core sync logic. Wrapped in semaphore acquisition.
        Runs blocking git checks in a thread executor to avoid blocking event loop.

        Args:
            account: Account configuration
            repo: Repository name or config
            progress: Optional callback for progress updates

        Returns:
            SyncResult with operation outcome
        """

        repo_name = repo.name if isinstance(repo, RepoConfig) else repo
        repo_remote = repo.remote_name if isinstance(repo, RepoConfig) else None
        repo_slug = repo_remote or repo_name
        path = self.config.get_repo_path(account.name, repo)

        async with self._semaphore:
            if progress:
                progress(f"Syncing {account.name}/{repo_name}", level="info")
            try:
                if self.github.repo_exists(path):
                    has_changes = await asyncio.to_thread(self.github.has_uncommitted_changes, path)
                    if has_changes:
                        message = f"Skipped {account.name}/{repo_name} due to uncommitted changes"
                        if progress:
                            progress(message, level="warning")
                        return SyncResult(
                            account=account.name,
                            repo=repo_name,
                            status="skipped",
                            message=message,
                            path=path,
                        )
                    if progress:
                        progress(f"Updating {account.name}/{repo_name}", level="info")
                    updated, message = await self.github.update_repo(path)
                    status = "updated" if updated else "up-to-date"
                    if progress:
                        progress(f"Updated {account.name}/{repo_name}", level="info")
                    return SyncResult(account=account.name, repo=repo_name, status=status, message=message, path=path)
                await self.github.clone_repo(account.name, repo_slug, path)
                if progress:
                    progress(f"Cloned {account.name}/{repo_name}", level="success")
                return SyncResult(account=account.name, repo=repo_name, status="cloned", path=path)
            except Exception as exc:  # noqa: BLE001 - report all errors
                if progress:
                    progress(f"Failed {account.name}/{repo_name}: {exc}", level="error")
                return SyncResult(
                    account=account.name,
                    repo=repo_name,
                    status="error",
                    message=str(exc),
                    path=path,
                )

    def list_repos(self) -> dict[str, list[tuple[str, Path, bool]]]:
        """List all configured repositories with status.

        Returns:
            Dict mapping account name to list of:
                (repo_name, local_path, exists)
        """

        results: dict[str, list[tuple[str, Path, bool]]] = {}
        for account in self.config.accounts:
            account_entries: list[tuple[str, Path, bool]] = []
            for repo in account.repos:
                repo_name = repo.name if isinstance(repo, RepoConfig) else repo
                path = self.config.get_repo_path(account.name, repo)
                account_entries.append((repo_name, path, self.github.repo_exists(path)))
            results[account.name] = account_entries
        return results
