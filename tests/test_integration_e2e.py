"""
End-to-end integration tests for repoman.

Tests the complete workflow: config file → clone → update → verify
Uses real GitHub repositories for validation.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import yaml

from repoman.config import RepomanConfig
from repoman.github import GitHubClient
from repoman.manager import RepoManager

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def integration_workspace(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary workspace for integration tests."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    workspace = tmp_path / f"repoman_e2e_{timestamp}"
    workspace.mkdir(parents=True, exist_ok=True)
    yield workspace


@pytest.fixture()
def skip_if_no_git() -> None:
    """Skip test if git is not available."""
    if shutil.which("git") is None:
        pytest.skip("git is required for integration tests")


@pytest.fixture()
def sample_config_file(integration_workspace: Path) -> Path:
    """Create a sample config file with real GitHub repos."""
    config_data = {
        "global": {
            "base_dir": str(integration_workspace / "repos"),
            "max_concurrent": 2,
            "use_ssh": False,
            "timeout": 300,
        },
        "accounts": [
            {
                "name": "octocat",
                "repos": [
                    "Hello-World",
                    "Spoon-Knife",
                ],
            },
            {
                "name": "github",
                "repos": [
                    {
                        "name": "gitignore",
                        "local_dir": str(integration_workspace / "custom" / "gitignore"),
                    },
                ],
            },
        ],
    }

    config_path = integration_workspace / "repoman.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config_data, f)

    return config_path


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_workflow_clone_and_update(
    sample_config_file: Path,
    integration_workspace: Path,
    skip_if_no_git: None,
) -> None:
    """
    Test the complete repoman workflow:
    1. Load config from file
    2. Clone repos based on config
    3. Verify cloned repos exist
    4. Run sync again (should update, not re-clone)
    5. Verify repos are up to date
    """
    # Step 1: Load config from file
    with open(sample_config_file) as f:
        config_dict = yaml.safe_load(f)

    config = RepomanConfig(**config_dict)

    # Verify config loaded correctly
    assert config.global_config.base_dir == integration_workspace / "repos"
    assert len(config.accounts) == 2
    assert config.accounts[0].name == "octocat"
    assert len(config.accounts[0].repos) == 2

    # Step 2: Create manager and perform initial sync (clone)
    github_client = GitHubClient(use_ssh=False, timeout=300)
    manager = RepoManager(config, github_client=github_client)

    progress_messages: list[str] = []

    def capture_progress(message: str, level: str = "info") -> None:
        progress_messages.append(f"[{level}] {message}")

    results = await manager.sync_all(progress=capture_progress)

    # Step 3: Verify all clones succeeded
    assert len(results) == 3

    successful_results = [r for r in results if r.status == "cloned"]
    assert len(successful_results) == 3

    # Verify repos exist on disk
    expected_paths = [
        integration_workspace / "repos" / "octocat" / "Hello-World",
        integration_workspace / "repos" / "octocat" / "Spoon-Knife",
        integration_workspace / "custom" / "gitignore",
    ]

    for path in expected_paths:
        assert path.exists(), f"Repository not found: {path}"
        assert (path / ".git").exists(), f"Not a git repository: {path}"

    # Verify progress messages were generated
    assert any("octocat/Hello-World" in msg for msg in progress_messages)

    # Step 4: Run sync again (should update, not re-clone)
    progress_messages.clear()
    results_update = await manager.sync_all(progress=capture_progress)

    # Step 5: Verify update behavior
    assert len(results_update) == 3

    statuses = {r.status for r in results_update}
    assert "cloned" not in statuses
    assert statuses <= {"up-to-date", "updated"}

    for path in expected_paths:
        assert path.exists()
        assert (path / ".git").exists()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mixed_success_and_failure(
    integration_workspace: Path,
    skip_if_no_git: None,
) -> None:
    """Test handling of both successful and failed clones."""
    config_data = {
        "global": {
            "base_dir": str(integration_workspace / "repos"),
            "max_concurrent": 2,
            "use_ssh": False,
            "timeout": 60,
        },
        "accounts": [
            {
                "name": "octocat",
                "repos": [
                    "Hello-World",
                    "definitely-does-not-exist-123456",
                ],
            },
        ],
    }

    config = RepomanConfig(**config_data)
    github_client = GitHubClient(use_ssh=False, timeout=60)
    manager = RepoManager(config, github_client=github_client)

    results = await manager.sync_all()

    assert len(results) == 2

    results_by_repo = {r.repo: r for r in results}

    assert results_by_repo["Hello-World"].status == "cloned"
    assert results_by_repo["definitely-does-not-exist-123456"].status == "error"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_custom_local_directory(
    integration_workspace: Path,
    skip_if_no_git: None,
) -> None:
    """Test that custom local_dir in RepoConfig is respected."""
    custom_path = integration_workspace / "my_custom_location" / "my_repo"

    config_data = {
        "global": {
            "base_dir": str(integration_workspace / "repos"),
            "use_ssh": False,
            "timeout": 300,
        },
        "accounts": [
            {
                "name": "octocat",
                "repos": [
                    {
                        "name": "Hello-World",
                        "local_dir": str(custom_path),
                    },
                ],
            },
        ],
    }

    config = RepomanConfig(**config_data)
    github_client = GitHubClient(use_ssh=False)
    manager = RepoManager(config, github_client=github_client)

    results = await manager.sync_all()

    assert len(results) == 1
    assert results[0].status == "cloned"

    assert custom_path.exists()
    assert (custom_path / ".git").exists()

    default_path = integration_workspace / "repos" / "octocat" / "Hello-World"
    assert not default_path.exists()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_account_level_base_dir_override(
    integration_workspace: Path,
    skip_if_no_git: None,
) -> None:
    """Ensure account-level base_dir overrides global base_dir."""
    global_base_dir = integration_workspace / "repos"
    account_base_dir = integration_workspace / "account_repos"

    config_data = {
        "global": {
            "base_dir": str(global_base_dir),
            "max_concurrent": 2,
            "use_ssh": False,
            "timeout": 300,
        },
        "accounts": [
            {"name": "octocat", "repos": ["Hello-World"]},
            {
                "name": "github",
                "base_dir": str(account_base_dir),
                "repos": ["gitignore"],
            },
        ],
    }

    config = RepomanConfig(**config_data)
    github_client = GitHubClient(use_ssh=False)
    manager = RepoManager(config, github_client=github_client)

    results = await manager.sync_all()

    assert len(results) == 2
    assert all(result.status == "cloned" for result in results)

    octocat_path = global_base_dir / "octocat" / "Hello-World"
    github_path = account_base_dir / "github" / "gitignore"
    github_global_path = global_base_dir / "github" / "gitignore"

    assert octocat_path.exists()
    assert (octocat_path / ".git").exists()
    assert github_path.exists()
    assert (github_path / ".git").exists()
    assert not github_global_path.exists()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_multiple_accounts_same_repo_name(
    integration_workspace: Path,
    skip_if_no_git: None,
) -> None:
    """Ensure repos with the same name across accounts clone into distinct paths."""
    config_data = {
        "global": {
            "base_dir": str(integration_workspace / "repos"),
            "max_concurrent": 2,
            "use_ssh": False,
            "timeout": 300,
        },
        "accounts": [
            {"name": "octocat", "repos": ["Hello-World"]},
            {"name": "Ameen-Alam", "repos": ["Hello-World"]},
        ],
    }

    config = RepomanConfig(**config_data)
    github_client = GitHubClient(use_ssh=False)
    manager = RepoManager(config, github_client=github_client)

    results = await manager.sync_all()

    assert len(results) == 2
    assert all(result.status == "cloned" for result in results)

    octocat_path = integration_workspace / "repos" / "octocat" / "Hello-World"
    github_path = integration_workspace / "repos" / "Ameen-Alam" / "Hello-World"

    assert octocat_path.exists()
    assert github_path.exists()
    assert octocat_path != github_path


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_clones_with_semaphore(
    integration_workspace: Path,
    skip_if_no_git: None,
) -> None:
    """Test that max_concurrent setting works correctly."""
    config_data = {
        "global": {
            "base_dir": str(integration_workspace / "repos"),
            "max_concurrent": 1,
            "use_ssh": False,
            "timeout": 300,
        },
        "accounts": [
            {
                "name": "octocat",
                "repos": [
                    "Hello-World",
                    "Spoon-Knife",
                    "git-consortium",
                ],
            },
        ],
    }

    config = RepomanConfig(**config_data)
    github_client = GitHubClient(use_ssh=False)
    manager = RepoManager(config, github_client=github_client)

    results = await manager.sync_all()

    assert len(results) == 3
    assert all(r.status == "cloned" for r in results)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_repos_with_shared_parent_dirs(
    integration_workspace: Path,
    skip_if_no_git: None,
) -> None:
    """Ensure concurrent clones under the same account succeed."""
    config_data = {
        "global": {
            "base_dir": str(integration_workspace / "repos"),
            "max_concurrent": 2,
            "use_ssh": False,
            "timeout": 300,
        },
        "accounts": [
            {
                "name": "octocat",
                "repos": [
                    "Hello-World",
                    "Spoon-Knife",
                ],
            },
        ],
    }

    config = RepomanConfig(**config_data)
    github_client = GitHubClient(use_ssh=False)
    manager = RepoManager(config, github_client=github_client)

    results = await manager.sync_all()

    assert len(results) == 2
    assert all(result.status == "cloned" for result in results)

    expected_paths = [
        integration_workspace / "repos" / "octocat" / "Hello-World",
        integration_workspace / "repos" / "octocat" / "Spoon-Knife",
    ]

    for path in expected_paths:
        assert path.exists()


@pytest.mark.integration
def test_config_file_with_comments(integration_workspace: Path) -> None:
    """Test that config file can contain YAML comments."""
    config_content = """
# This is a comment
global:
  base_dir: ~/repos
  max_concurrent: 3
  timeout: 300

accounts:
  - name: test_user
    repos:
      - repo1
      - repo2
"""

    config_path = integration_workspace / "repoman.yaml"
    config_path.write_text(config_content)

    with open(config_path) as f:
        config_dict = yaml.safe_load(f)

    config = RepomanConfig(**config_dict)

    assert config.global_config.max_concurrent == 3
    assert len(config.accounts[0].repos) == 2
