# src/repoman/github.py
"""GitHub operations for repoman."""

from __future__ import annotations

from pathlib import Path
import asyncio
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

    Clone/update operations are async. Manager layer handles coordination.
    """

    def __init__(self, use_ssh: bool = True, timeout: int = 300) -> None:
        """Initialize GitHub client.

        Args:
            use_ssh: Use SSH URLs (git@github.com:) instead of HTTPS
            timeout: Timeout in seconds for git operations
        """

        if not 30 <= timeout <= 3600:
            raise ValueError("timeout must be between 30 and 3600 seconds")

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

    async def _run_git_command(self, args: list[str], timeout: int | None = None) -> tuple[str, str]:
        """Run a git command asynchronously and return stdout/stderr.

        Args:
            args: Command arguments (including "git").
            timeout: Timeout in seconds.

        Returns:
            Tuple of (stdout, stderr).

        Raises:
            GitNotFoundError: If git command not found.
            subprocess.TimeoutExpired: If command exceeds timeout.
            RuntimeError: If command exits with nonzero status.
        """

        try:
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise GitNotFoundError("git command not found. Please install git.") from exc

        resolved_timeout = self.timeout if timeout is None else timeout
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=resolved_timeout,
            )
        except asyncio.TimeoutError as exc:
            process.kill()
            await process.wait()
            raise subprocess.TimeoutExpired(cmd=args, timeout=resolved_timeout) from exc

        stdout = stdout_bytes.decode().strip() if stdout_bytes else ""
        stderr = stderr_bytes.decode().strip() if stderr_bytes else ""

        if process.returncode != 0:
            message = stderr or "git command failed"
            raise RuntimeError(message)

        return stdout, stderr

    async def clone_repo(self, account: str, repo: str, dest: Path) -> None:
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
            await self._run_git_command(["git", "clone", url, str(dest)])
        except subprocess.TimeoutExpired as exc:
            raise CloneError(f"git clone timed out after {self.timeout} seconds") from exc
        except RuntimeError as exc:
            message = str(exc).strip()
            if message:
                raise CloneError(f"Failed to clone {url}: {message}") from exc
            raise CloneError("git clone failed") from exc

    async def update_repo(self, path: Path) -> tuple[bool, str]:
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
            stdout, _stderr = await self._run_git_command(["git", "-C", str(path), "pull"])
        except subprocess.TimeoutExpired as exc:
            raise UpdateError(f"git pull timed out after {self.timeout} seconds") from exc
        except RuntimeError as exc:
            message = str(exc).strip()
            if message:
                raise UpdateError(f"Failed to update {path}: {message}") from exc
            raise UpdateError("git pull failed") from exc

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
                timeout=5,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

        if result.returncode != 0:
            return False

        return bool(result.stdout.strip())

    def get_current_branch(self, path: Path) -> str | None:
        """Get the current git branch for a repository.

        Args:
            path: Path to existing git repository

        Returns:
            The current branch name, or None on failure.

        Raises:
            UpdateError: If path doesn't exist or isn't a git repo
        """

        if not path.exists():
            raise UpdateError(f"Repository path does not exist: {path}")
        if not (path / ".git").is_dir():
            raise UpdateError(f"Path is not a git repository: {path}")

        try:
            result = subprocess.run(
                ["git", "-C", str(path), "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None

        if result.returncode != 0:
            return None

        branch = result.stdout.strip()
        return branch or None
