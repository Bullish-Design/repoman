"""RepoMan's repository-specific Devman manifest migration tests."""

from __future__ import annotations

import pytest

from repoman.devman.migrate import MigrationError, apply_migration, derive_manifest, inspect_migration

NIX = """{ pkgs, ... }:
{
  devman = {
    enable = true;
    project = "fixture";
    groups = [ "base" "format" ];
  };
}
"""


def test_derives_portable_manifest_facts_from_devenv(tmp_path):
    (tmp_path / "devenv.nix").write_text(NIX)

    proposal = derive_manifest(tmp_path)

    assert proposal.project == "fixture"
    assert proposal.groups == ("base", "format")
    assert "path" not in proposal.to_toml()


def test_inspection_does_not_write_and_apply_is_idempotent(tmp_path):
    (tmp_path / "devenv.nix").write_text(NIX)

    proposed = inspect_migration(tmp_path)
    assert proposed.state == "needed"
    assert not (tmp_path / ".devman/project.toml").exists()

    written = apply_migration(tmp_path)
    again = apply_migration(tmp_path)
    assert written.state == "written"
    assert again.state == "current"
    assert (tmp_path / ".devman/project.toml").read_text() == written.content


def test_different_existing_manifest_is_preserved_without_force(tmp_path):
    (tmp_path / "devenv.nix").write_text(NIX)
    manifest = tmp_path / ".devman/project.toml"
    manifest.parent.mkdir()
    manifest.write_text('schema = 1\nproject = "other"\ngroups = ["base"]\npolicy = "stable"\n')

    with pytest.raises(MigrationError, match="differs"):
        apply_migration(tmp_path)

    assert 'project = "other"' in manifest.read_text()


def test_disabled_devman_is_not_migrated(tmp_path):
    (tmp_path / "devenv.nix").write_text(NIX.replace("enable = true", "enable = false"))

    with pytest.raises(MigrationError, match="must be true"):
        derive_manifest(tmp_path)
