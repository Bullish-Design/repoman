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


@pytest.fixture()
def test_output_dir() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = f"{timestamp}_{os.getpid()}"
    base_dir = Path(__file__).resolve().parent / "test_output" / suffix
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


@pytest.fixture()
def hello_world_repo(test_output_dir: Path) -> Path:
    if shutil.which("git") is None:
        pytest.skip("git is required for integration tests")
    client = GitHubClient(use_ssh=False)
    dest = test_output_dir / "octocat-hello-world"
    if not dest.exists():
        client.clone_repo("octocat", "Hello-World", dest)
    return dest


def test_clone_repo_real_github(hello_world_repo: Path) -> None:
    assert (hello_world_repo / ".git").is_dir()


def test_clone_repo_missing_git(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = GitHubClient()

    def _fake_run(*_args: object, **_kwargs: object) -> _Result:
        raise FileNotFoundError

    monkeypatch.setattr("subprocess.run", _fake_run)
    with pytest.raises(GitNotFoundError):
        client.clone_repo("acct", "repo", tmp_path / "dest")


def test_clone_repo_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = GitHubClient()

    def _fake_run(*_args: object, **_kwargs: object) -> _Result:
        raise subprocess.TimeoutExpired(cmd=["git"], timeout=client.timeout)

    monkeypatch.setattr("subprocess.run", _fake_run)
    with pytest.raises(CloneError, match="timed out"):
        client.clone_repo("acct", "repo", tmp_path / "dest")


def test_clone_repo_failure_includes_stderr(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = GitHubClient()

    def _fake_run(*_args: object, **_kwargs: object) -> _Result:
        return _Result(returncode=1, stderr="clone failed")

    monkeypatch.setattr("subprocess.run", _fake_run)
    with pytest.raises(CloneError, match="clone failed"):
        client.clone_repo("acct", "repo", tmp_path / "dest")


def test_update_repo_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = GitHubClient()

    with pytest.raises(UpdateError):
        client.update_repo(tmp_path / "missing")

    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    with pytest.raises(UpdateError):
        client.update_repo(repo_path)

    (repo_path / ".git").mkdir()

    def _fake_run(*_args: object, **_kwargs: object) -> _Result:
        return _Result(returncode=1, stderr="pull failed")

    monkeypatch.setattr("subprocess.run", _fake_run)
    with pytest.raises(UpdateError, match="pull failed"):
        client.update_repo(repo_path)


def test_update_repo_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = GitHubClient()
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()

    def _fake_run(*_args: object, **_kwargs: object) -> _Result:
        raise subprocess.TimeoutExpired(cmd=["git"], timeout=client.timeout)

    monkeypatch.setattr("subprocess.run", _fake_run)
    with pytest.raises(UpdateError, match="timed out"):
        client.update_repo(repo_path)


def test_update_repo_up_to_date(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = GitHubClient()
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()

    def _fake_run(*_args: object, **_kwargs: object) -> _Result:
        return _Result(returncode=0, stdout="Already up to date.")

    monkeypatch.setattr("subprocess.run", _fake_run)
    updated, message = client.update_repo(repo_path)
    assert updated is False
    assert "Already up to date" in message


def test_update_repo_real_github(hello_world_repo: Path) -> None:
    client = GitHubClient(use_ssh=False)
    updated, message = client.update_repo(hello_world_repo)
    assert updated is False
    assert message


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
