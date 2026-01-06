# src/repoman/config.py
"""Configuration models for repoman."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field, ValidationError, field_validator

_REPO_NAME_PATTERN = r"^[A-Za-z0-9._-]+$"


def _expand_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    return Path(value).expanduser().resolve()


def _validate_repo_name(name: str) -> str:
    if not name:
        raise ValueError("Repository name must not be empty")
    if "/" in name:
        raise ValueError("Repository name must not contain slashes")
    if not Path(name).name == name:
        raise ValueError("Repository name must not contain path separators")
    import re

    if not re.match(_REPO_NAME_PATTERN, name):
        raise ValueError("Repository name must contain only letters, numbers, dots, underscores, or dashes")
    return name


class RepoConfig(BaseModel):
    """Configuration for a single repository.

    Attributes:
        name: Repository name (not including owner)
        local_dir: Optional override for repository location
    """

    name: str
    local_dir: Path | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _validate_repo_name(value)

    @field_validator("local_dir", mode="before")
    @classmethod
    def expand_path(cls, value: str | Path | None) -> Path | None:
        """Expand ~ and resolve to absolute path."""

        return _expand_path(value)


class AccountConfig(BaseModel):
    """Configuration for a GitHub account.

    Attributes:
        name: GitHub username or organization name
        repos: List of repositories (string names or RepoConfig objects)
        base_dir: Optional override for this account's base directory
    """

    name: str
    repos: list[str | RepoConfig]
    base_dir: Path | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value or value.strip() == "":
            raise ValueError("Account name must not be empty")
        return value

    @field_validator("base_dir", mode="before")
    @classmethod
    def expand_path(cls, value: str | Path | None) -> Path | None:
        """Expand ~ and resolve to absolute path."""

        return _expand_path(value)

    @field_validator("repos", mode="before")
    @classmethod
    def normalize_repos(cls, value: list[str | dict | RepoConfig]) -> list[str | RepoConfig]:
        """Convert dict entries to RepoConfig objects."""

        if value is None:
            return value
        normalized: list[str | RepoConfig] = []
        for item in value:
            if isinstance(item, dict):
                normalized.append(RepoConfig.model_validate(item))
            else:
                normalized.append(item)
        return normalized

    @field_validator("repos")
    @classmethod
    def validate_repos(cls, value: list[str | RepoConfig]) -> list[str | RepoConfig]:
        if not value:
            raise ValueError("Account must contain at least one repository")
        for repo in value:
            if isinstance(repo, str):
                _validate_repo_name(repo)
        return value


class GlobalConfig(BaseModel):
    """Global configuration settings.

    Attributes:
        base_dir: Default base directory for all repositories
        max_concurrent: Maximum concurrent git operations
    """

    base_dir: Annotated[Path, Field(default=Path("~/code"))]
    max_concurrent: Annotated[int, Field(default=5, ge=1, le=20)]

    @field_validator("base_dir", mode="before")
    @classmethod
    def expand_path(cls, value: str | Path) -> Path:
        """Expand ~ and resolve to absolute path."""

        expanded = _expand_path(value)
        if expanded is None:
            raise ValueError("Base directory must be a valid path")
        return expanded


class RepomanConfig(BaseModel):
    """Root configuration for repoman.

    Attributes:
        global_config: Global settings
        accounts: List of account configurations
    """

    global_config: Annotated[GlobalConfig, Field(alias="global")] = GlobalConfig()
    accounts: list[AccountConfig] = []

    def get_repo_path(self, account: str, repo: str | RepoConfig) -> Path:
        """Calculate final local path for a repository.

        Resolution order:
        1. RepoConfig.local_dir if specified
        2. AccountConfig.base_dir / account / repo_name
        3. GlobalConfig.base_dir / account / repo_name

        Args:
            account: GitHub account name
            repo: Repository name or config object

        Returns:
            Absolute path where repository should be located

        Raises:
            ValueError: If account not found in configuration
        """

        account_config = next((item for item in self.accounts if item.name == account), None)
        if account_config is None:
            raise ValueError(f"Account {account} not found in configuration")

        repo_name = repo.name if isinstance(repo, RepoConfig) else repo
        if isinstance(repo, RepoConfig) and repo.local_dir is not None:
            return repo.local_dir

        base_dir = account_config.base_dir or self.global_config.base_dir
        return base_dir / account_config.name / repo_name


def parse_config(data: dict) -> RepomanConfig:
    """Parse configuration data into RepomanConfig with helpful errors."""

    try:
        return RepomanConfig.model_validate(data)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
