# src/repoman/github.py
"""GitHub operations for repoman."""

from __future__ import annotations

from pathlib import Path
import subprocess


class GitHubError(Exception):
    """Base exception for GitHub operations."""


class CloneError(GitHubError):
    """Raised when git clone fails."""


class UpdateError(GitHubError):
    """Raised when git pull fails."""


class GitNotFoundError(GitHubError):
    """Raised when git command is not available."""


class GitHubClient:
    """Client for GitHub repository operations using git commands.

    All operations are synchronous. Manager layer handles async coordination.
    """

    def __init__(self, use_ssh: bool = True, timeout: int = 300) -> None:
        """Initialize GitHub client.

        Args:
            use_ssh: Use SSH URLs (git@github.com:) instead of HTTPS
            timeout: Timeout in seconds for git operations
        """

        self.use_ssh = use_ssh
        self.timeout = timeout

    def get_repo_url(self, account: str, repo: str) -> str:
        """Construct repository clone URL.

        Args:
            account: GitHub username or organization
            repo: Repository name

        Returns:
            SSH URL: git@github.com:account/repo.git
            HTTPS URL: https://github.com/account/repo.git
        """

        if self.use_ssh:
            return f"git@github.com:{account}/{repo}.git"
        return f"https://github.com/{account}/{repo}.git"

    def clone_repo(self, account: str, repo: str, dest: Path) -> None:
        """Clone repository to destination path.

        Creates parent directories if needed.

        Args:
            account: GitHub username or organization
            repo: Repository name
            dest: Destination path for repository

        Raises:
            CloneError: If clone operation fails
            GitNotFoundError: If git command not found
        """

        dest.parent.mkdir(parents=True, exist_ok=True)
        url = self.get_repo_url(account, repo)
        try:
            result = subprocess.run(
                ["git", "clone", url, str(dest)],
                capture_output=True,
                text=True,
                check=False,
                timeout=self.timeout,
            )
        except FileNotFoundError as exc:
            raise GitNotFoundError("git command not found. Please install git.") from exc
        except subprocess.TimeoutExpired as exc:
            raise CloneError("git clone timed out") from exc

        if result.returncode != 0:
            raise CloneError(result.stderr.strip() or "git clone failed")

    def update_repo(self, path: Path) -> tuple[bool, str]:
        """Update repository with git pull.

        Args:
            path: Path to existing git repository

        Returns:
            Tuple of (updated, message):
                updated: True if changes were pulled, False if already up-to-date
                message: Git output message

        Raises:
            UpdateError: If path doesn't exist or isn't a git repo
            UpdateError: If git pull fails
            GitNotFoundError: If git command not found
        """

        if not path.exists():
            raise UpdateError(f"Repository path does not exist: {path}")
        if not (path / ".git").is_dir():
            raise UpdateError(f"Path is not a git repository: {path}")

        try:
            result = subprocess.run(
                ["git", "-C", str(path), "pull"],
                capture_output=True,
                text=True,
                check=False,
                timeout=self.timeout,
            )
        except FileNotFoundError as exc:
            raise GitNotFoundError("git command not found. Please install git.") from exc
        except subprocess.TimeoutExpired as exc:
            raise UpdateError("git pull timed out") from exc

        if result.returncode != 0:
            raise UpdateError(result.stderr.strip() or "git pull failed")

        stdout = result.stdout.strip()
        lowered = stdout.lower()
        updated = not ("already up to date" in lowered or "already up-to-date" in lowered)
        return updated, stdout

    def repo_exists(self, path: Path) -> bool:
        """Check if repository exists at path.

        Args:
            path: Path to check

        Returns:
            True if path exists and contains .git directory
        """

        return path.is_dir() and (path / ".git").is_dir()

    def has_uncommitted_changes(self, path: Path) -> bool:
        """Check if repository has uncommitted changes.

        Args:
            path: Path to existing git repository

        Returns:
            True if repository has uncommitted changes, False otherwise

        Raises:
            UpdateError: If path doesn't exist or isn't a git repo
            GitNotFoundError: If git command not found
        """

        if not path.exists():
            raise UpdateError(f"Repository path does not exist: {path}")
        if not (path / ".git").is_dir():
            raise UpdateError(f"Path is not a git repository: {path}")

        try:
            result = subprocess.run(
                ["git", "-C", str(path), "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=False,
                timeout=self.timeout,
            )
        except FileNotFoundError as exc:
            raise GitNotFoundError("git command not found. Please install git.") from exc
        except subprocess.TimeoutExpired as exc:
            raise UpdateError("git status timed out") from exc

        if result.returncode != 0:
            raise UpdateError(result.stderr.strip() or "git status failed")

        return bool(result.stdout.strip())
