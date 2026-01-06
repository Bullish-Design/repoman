from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from repoman.github import CloneError, GitHubClient, GitNotFoundError, UpdateError


class _Result:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class _Process:
    def __init__(self, returncode: int, stdout: bytes = b"", stderr: bytes = b"") -> None:
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    async def communicate(self) -> tuple[bytes, bytes]:
        return self._stdout, self._stderr

    async def wait(self) -> int:
        return self.returncode

    def kill(self) -> None:
        return None


def test_get_repo_url() -> None:
    ssh_client = GitHubClient(use_ssh=True)
    https_client = GitHubClient(use_ssh=False)

    assert ssh_client.get_repo_url("acct", "repo") == "git@github.com:acct/repo.git"
    assert https_client.get_repo_url("acct", "repo") == "https://github.com/acct/repo.git"


def test_repo_exists(tmp_path: Path) -> None:
    client = GitHubClient()
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    assert client.repo_exists(repo_path) is False
    (repo_path / ".git").mkdir()
    assert client.repo_exists(repo_path) is True


def test_github_client_validates_timeout_too_low() -> None:
    with pytest.raises(ValueError, match="timeout must be between 30 and 3600 seconds"):
        GitHubClient(timeout=29)


def test_github_client_validates_timeout_too_high() -> None:
    with pytest.raises(ValueError, match="timeout must be between 30 and 3600 seconds"):
        GitHubClient(timeout=3601)


def test_github_client_accepts_valid_timeout() -> None:
    for timeout in (30, 300, 3600):
        client = GitHubClient(timeout=timeout)
        assert client.timeout == timeout


@pytest.fixture()
def test_output_dir() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = f"{timestamp}_{os.getpid()}"
    base_dir = Path(__file__).resolve().parent / "test_output" / suffix
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


@pytest.fixture()
async def hello_world_repo(test_output_dir: Path) -> Path:
    if shutil.which("git") is None:
        pytest.skip("git is required for integration tests")
    client = GitHubClient(use_ssh=False)
    dest = test_output_dir / "octocat-hello-world"
    if not dest.exists():
        await client.clone_repo("octocat", "Hello-World", dest)
    return dest


@pytest.mark.asyncio
async def test_clone_repo_real_github(hello_world_repo: Path) -> None:
    assert (hello_world_repo / ".git").is_dir()


@pytest.mark.asyncio
async def test_clone_repo_missing_git(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = GitHubClient()

    async def _fake_create_subprocess_exec(*_args: object, **_kwargs: object) -> _Process:
        raise FileNotFoundError

    monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_create_subprocess_exec)
    with pytest.raises(GitNotFoundError):
        await client.clone_repo("acct", "repo", tmp_path / "dest")


@pytest.mark.asyncio
async def test_clone_repo_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = GitHubClient()

    async def _fake_run_git_command(*_args: object, **_kwargs: object) -> tuple[str, str]:
        raise subprocess.TimeoutExpired(cmd=["git"], timeout=client.timeout)

    monkeypatch.setattr(client, "_run_git_command", _fake_run_git_command)
    with pytest.raises(CloneError, match="timed out"):
        await client.clone_repo("acct", "repo", tmp_path / "dest")


@pytest.mark.asyncio
async def test_clone_repo_failure_includes_stderr(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = GitHubClient()

    async def _fake_create_subprocess_exec(*_args: object, **_kwargs: object) -> _Process:
        return _Process(returncode=1, stderr=b"clone failed")

    monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_create_subprocess_exec)
    with pytest.raises(CloneError, match="clone failed"):
        await client.clone_repo("acct", "repo", tmp_path / "dest")


@pytest.mark.asyncio
async def test_update_repo_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = GitHubClient()

    with pytest.raises(UpdateError):
        await client.update_repo(tmp_path / "missing")

    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    with pytest.raises(UpdateError):
        await client.update_repo(repo_path)

    (repo_path / ".git").mkdir()

    async def _fake_create_subprocess_exec(*_args: object, **_kwargs: object) -> _Process:
        return _Process(returncode=1, stderr=b"pull failed")

    monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_create_subprocess_exec)
    with pytest.raises(UpdateError, match="pull failed"):
        await client.update_repo(repo_path)


@pytest.mark.asyncio
async def test_update_repo_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = GitHubClient()
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()

    async def _fake_run_git_command(*_args: object, **_kwargs: object) -> tuple[str, str]:
        raise subprocess.TimeoutExpired(cmd=["git"], timeout=client.timeout)

    monkeypatch.setattr(client, "_run_git_command", _fake_run_git_command)
    with pytest.raises(UpdateError, match="timed out"):
        await client.update_repo(repo_path)


@pytest.mark.asyncio
async def test_update_repo_up_to_date(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = GitHubClient()
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()

    async def _fake_create_subprocess_exec(*_args: object, **_kwargs: object) -> _Process:
        return _Process(returncode=0, stdout=b"Already up to date.")

    monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_create_subprocess_exec)
    updated, message = await client.update_repo(repo_path)
    assert updated is False
    assert "Already up to date" in message


@pytest.mark.asyncio
async def test_update_repo_real_github(hello_world_repo: Path) -> None:
    client = GitHubClient(use_ssh=False)
    updated, message = await client.update_repo(hello_world_repo)
    assert updated is False
    assert message


@pytest.mark.asyncio
async def test_run_git_command_nonzero_exit_raises_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = GitHubClient()

    async def _fake_create_subprocess_exec(*_args: object, **_kwargs: object) -> _Process:
        return _Process(returncode=2, stderr=b"bad exit")

    monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_create_subprocess_exec)

    with pytest.raises(RuntimeError, match="bad exit"):
        await client._run_git_command(["git", "status"])


def test_has_uncommitted_changes_true(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = GitHubClient()
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()

    def _fake_run(*_args: object, **_kwargs: object) -> _Result:
        return _Result(returncode=0, stdout=" M file.txt\n")

    monkeypatch.setattr("subprocess.run", _fake_run)
    assert client.has_uncommitted_changes(repo_path) is True


def test_get_current_branch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = GitHubClient()
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()

    def _fake_run_success(*_args: object, **_kwargs: object) -> _Result:
        return _Result(returncode=0, stdout="main\n")

    monkeypatch.setattr("subprocess.run", _fake_run_success)
    assert client.get_current_branch(repo_path) == "main"

    def _fake_run_failure(*_args: object, **_kwargs: object) -> _Result:
        return _Result(returncode=1, stderr="error")

    monkeypatch.setattr("subprocess.run", _fake_run_failure)
    assert client.get_current_branch(repo_path) is None
