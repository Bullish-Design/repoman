from __future__ import annotations

from pathlib import Path

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


def test_clone_repo_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = GitHubClient()

    def _fake_run(*_args: object, **_kwargs: object) -> _Result:
        return _Result(returncode=1, stderr="failed")

    monkeypatch.setattr("subprocess.run", _fake_run)
    with pytest.raises(CloneError):
        client.clone_repo("acct", "repo", tmp_path / "dest")


def test_clone_repo_missing_git(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = GitHubClient()

    def _fake_run(*_args: object, **_kwargs: object) -> _Result:
        raise FileNotFoundError

    monkeypatch.setattr("subprocess.run", _fake_run)
    with pytest.raises(GitNotFoundError):
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
    with pytest.raises(UpdateError):
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
