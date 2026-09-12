"""RepoMan-owned migration of the Devman project manifest."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path


class MigrationError(ValueError):
    """A repository cannot be migrated from its current Devman options."""


_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


@dataclass(frozen=True)
class ManifestProposal:
    """Portable manifest facts derived from one repository's current options."""

    project: str
    groups: tuple[str, ...]
    source: Path

    def to_toml(self) -> str:
        groups = ", ".join(f'"{group}"' for group in self.groups)
        return (
            "schema = 1\n"
            f'project = "{self.project}"\n'
            f"groups = [{groups}]\n"
            'policy = "stable"\n'
        )


@dataclass(frozen=True)
class MigrationResult:
    """The reviewable result of one migration inspection or application."""

    proposal: ManifestProposal
    path: Path
    state: str
    content: str


def derive_manifest(root: Path) -> ManifestProposal:
    """Derive a manifest proposal from the repository's ``devman`` block."""

    repository = root.expanduser().resolve()
    source = repository / "devenv.nix"
    try:
        text = source.read_text()
    except OSError as exc:
        raise MigrationError(f"cannot read {source}: {exc}") from exc

    blocks = re.findall(r"\bdevman\s*=\s*\{(?P<body>.*?)\n\s*\};", text, re.DOTALL)
    if len(blocks) != 1:
        raise MigrationError(
            f"expected one devman option block in {source}, found {len(blocks)}"
        )
    body = blocks[0]
    enabled = re.search(r"\benable\s*=\s*(true|false)\s*;", body)
    if enabled is None or enabled.group(1) != "true":
        raise MigrationError(f"{source}: devman.enable must be true for migration")
    project = _single_string(body, "project", source)
    _validate_reference("project", project, source)
    groups_match = re.search(r"\bgroups\s*=\s*\[(?P<values>.*?)\]", body, re.DOTALL)
    if groups_match is None:
        raise MigrationError(f"{source}: devman.groups is required for migration")
    groups = tuple(re.findall(r'"([^"\\]+)"', groups_match.group("values")))
    if not groups:
        raise MigrationError(f"{source}: devman.groups must not be empty")
    if len(set(groups)) != len(groups):
        raise MigrationError(f"{source}: devman.groups contains duplicate names")
    for group in groups:
        _validate_reference("group", group, source)
    return ManifestProposal(project=project, groups=groups, source=source)


def inspect_migration(root: Path) -> MigrationResult:
    """Report whether the repository needs a manifest migration."""

    repository = root.expanduser().resolve()
    proposal = derive_manifest(repository)
    path = repository / ".devman" / "project.toml"
    content = proposal.to_toml()
    if not path.exists():
        state = "needed"
    else:
        try:
            state = "current" if path.read_text() == content else "different"
        except OSError as exc:
            raise MigrationError(f"cannot read existing manifest {path}: {exc}") from exc
    return MigrationResult(proposal, path, state, content)


def apply_migration(root: Path, *, force: bool = False) -> MigrationResult:
    """Write a new manifest without touching any other repository file.

    The caller still reviews and commits this tracked file through its normal
    repository workflow. RepoMan never edits ``devenv.nix`` or creates a
    machine-plane generation as part of this operation.
    """

    result = inspect_migration(root)
    if result.state == "current":
        return result
    if result.state == "different" and not force:
        raise MigrationError(
            f"{result.path} differs from the derived options; review it or pass --force"
        )
    result.path.parent.mkdir(parents=True, exist_ok=True)
    temporary = result.path.with_name(f".{result.path.name}.new")
    temporary.write_text(result.content)
    os.replace(temporary, result.path)
    return MigrationResult(result.proposal, result.path, "written", result.content)


def _single_string(body: str, key: str, source: Path) -> str:
    matches = re.findall(rf"\b{re.escape(key)}\s*=\s*\"([^\"\\]+)\"\s*;", body)
    if len(matches) != 1 or not matches[0]:
        raise MigrationError(f"{source}: devman.{key} must be one non-empty string")
    return matches[0]


def _validate_reference(kind: str, value: str, source: Path) -> None:
    if not _REFERENCE.fullmatch(value):
        raise MigrationError(
            f"{source}: devman {kind} {value!r} is not a portable identity"
        )
