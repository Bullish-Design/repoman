"""Tests for RepoMan's agent-surface link lint.

The central devman overlay owns `.agents/`. This namespace classifies what is
under `.agents/skills/`: the pool-link set the enabled roster expects vs
project-specific or overlay skills.
"""

from __future__ import annotations

import os

from repoman.checks import self_check_exit
from repoman.devman.check import expected_skills, skill_ownership_checks

ALL = ["copy", "git", "test", "doc"]
SKILLS = ".agents/skills"


def _names(result):
    return {c.name: c for c in result}


def _layout(tmp_path):
    """Build the central-overlay shape: ``repo/.agents -> central/projects/p/agents``.

    Returns ``(repo_root, skills_dir, pool)`` where ``skills_dir`` is the real
    project central dir and ``pool`` is the shared pool one level above it.
    """

    central = tmp_path / "central"
    project_agents = central / "projects" / "p" / "agents"
    (project_agents / "skills").mkdir(parents=True, exist_ok=True)
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    os.symlink(project_agents, repo / ".agents")
    return repo, project_agents / "skills", central / "skills"


def _link_pool_skill(pool, skills, name):
    target = pool / name
    target.mkdir(parents=True, exist_ok=True)
    (target / "SKILL.md").write_text(f"---\nname: {name}\n---\n")
    os.symlink(f"../../../../skills/{name}", skills / name)


def _real_skill(skills, name):
    skill = skills / name
    skill.mkdir(parents=True, exist_ok=True)
    (skill / "SKILL.md").write_text(f"---\nname: {name}\n---\n")


def _shipped(repo, enabled):
    return _names(skill_ownership_checks(repo, SKILLS, enabled))["skill:tool-shipped"]


def test_expected_set_follows_roster():
    assert expected_skills([]) == ("writing",)
    assert expected_skills(["git"]) == ("gitman", "writing")
    assert expected_skills(["copy"]) == ("copyroom", "copyroom-adopt", "copyroom-template-edit", "writing")
    assert expected_skills(["test", "doc"]) == ("docman", "testee", "writing")
    assert set(expected_skills(ALL)) == {
        "copyroom",
        "copyroom-adopt",
        "copyroom-template-edit",
        "docman",
        "gitman",
        "testee",
        "writing",
    }
    assert expected_skills(["nope"]) == ("writing",)


def test_gitman_v2_expects_its_own_skill_only(tmp_path):
    assert expected_skills(["git"], gitman_version=2) == ("gitman-v2", "writing")
    repo, skills, pool = _layout(tmp_path)
    for name in ("gitman-v2", "writing"):
        _link_pool_skill(pool, skills, name)
    row = _names(skill_ownership_checks(repo, SKILLS, ["git"], gitman_version=2))["skill:tool-shipped"]
    assert row.level == "ok"


def test_warns_when_skills_dir_missing(tmp_path):
    row = _names(skill_ownership_checks(tmp_path, SKILLS, ALL))["skill:tool-shipped"]
    assert row.level == "warn"
    assert "pool" in row.detail
    # The old remediation named copyroom's deleted export surface.
    assert "copyroom agent-files export" not in row.detail


def test_warns_when_a_manager_link_is_missing(tmp_path):
    repo, skills, _pool = _layout(tmp_path)
    for name in expected_skills(ALL):
        if name != "gitman":
            _real_skill(skills, name)
    row = _shipped(repo, ALL)
    assert row.level == "warn"
    assert "gitman" in row.detail
    assert "ln -s" in row.detail


def test_symlinked_pool_skills_register_as_present(tmp_path):
    repo, skills, pool = _layout(tmp_path)
    for name in expected_skills(ALL):
        _link_pool_skill(pool, skills, name)
    assert _shipped(repo, ALL).level == "ok"


def test_dangling_pool_link_does_not_register(tmp_path):
    repo, skills, _pool = _layout(tmp_path)
    for name in expected_skills(ALL):
        if name == "gitman":
            os.symlink("../../../../skills/gitman", skills / name)
            continue
        _real_skill(skills, name)
    assert _shipped(repo, ALL).level == "warn"


def test_real_directory_counts_as_present(tmp_path):
    repo, skills, _pool = _layout(tmp_path)
    for name in expected_skills(ALL):
        _real_skill(skills, name)
    assert _shipped(repo, ALL).level == "ok"


def test_project_specific_skills_reported_present(tmp_path):
    repo, skills, _pool = _layout(tmp_path)
    for name in (*expected_skills(ALL), "repoman", "devenv-run-commands", "repo-local"):
        _real_skill(skills, name)
    names = _names(skill_ownership_checks(repo, SKILLS, ALL))
    assert names["skill:tool-shipped"].level == "ok"
    row = names["skill:genome-overlay"]
    assert row.level == "ok"
    assert "devenv-run-commands" in row.detail
    assert "repo-local" in row.detail
    # The entrypoint is RepoMan's own — never classified as genome/overlay.
    assert "repoman" not in row.detail


def test_unselected_manager_skill_is_overlay(tmp_path):
    repo, skills, _pool = _layout(tmp_path)
    for name in (*expected_skills(["git"]), "testee"):
        _real_skill(skills, name)
    names = _names(skill_ownership_checks(repo, SKILLS, ["git"]))
    assert names["skill:tool-shipped"].level == "ok"
    assert "testee" in names["skill:genome-overlay"].detail


def test_git_only_roster_does_not_warn_about_other_managers(tmp_path):
    repo, skills, _pool = _layout(tmp_path)
    for name in ("gitman", "writing"):
        _real_skill(skills, name)
    row = _shipped(repo, ["git"])
    assert row.level == "ok"
    for name in ("copyroom", "testee", "docman"):
        assert name not in row.detail


def test_git_only_roster_missing_gitman_names_only_gitman(tmp_path):
    repo, skills, _pool = _layout(tmp_path)
    _real_skill(skills, "writing")
    row = _shipped(repo, ["git"])
    assert row.level == "warn"
    assert "['gitman']" in row.detail


def test_copy_roster_expects_copyroom_sub_skills(tmp_path):
    repo, skills, _pool = _layout(tmp_path)
    for name in ("copyroom", "writing"):
        _real_skill(skills, name)
    row = _shipped(repo, ["copy"])
    assert row.level == "warn"
    assert "copyroom-adopt" in row.detail
    assert "copyroom-template-edit" in row.detail
    for name in ("copyroom-adopt", "copyroom-template-edit"):
        _real_skill(skills, name)
    assert _shipped(repo, ["copy"]).level == "ok"


def test_sub_skills_not_expected_without_copy(tmp_path):
    repo, skills, _pool = _layout(tmp_path)
    for name in ("gitman", "writing"):
        _real_skill(skills, name)
    assert "copyroom" not in _shipped(repo, ["git"]).detail


def test_writing_expected_under_every_roster(tmp_path):
    for roster in ([], ["git"], ["copy"], ["copy", "git"], ALL):
        sub = tmp_path / "-".join(roster or ["empty"])
        sub.mkdir()
        repo, skills, _pool = _layout(sub)
        for name in expected_skills(roster):
            if name != "writing":
                _real_skill(skills, name)
        row = _shipped(repo, roster)
        assert row.level == "warn", roster
        assert "writing" in row.detail, roster
        _real_skill(skills, "writing")
        assert _shipped(repo, roster).level == "ok", roster


def test_empty_roster_expects_only_writing(tmp_path):
    repo, skills, _pool = _layout(tmp_path)
    _real_skill(skills, "writing")
    assert _shipped(repo, []).level == "ok"


def test_warn_is_non_fatal(tmp_path):
    result = skill_ownership_checks(tmp_path, SKILLS, ALL)
    assert self_check_exit(result) == 0
    repo, _skills, _pool = _layout(tmp_path)
    result = skill_ownership_checks(repo, SKILLS, ALL)
    assert {c.level for c in result} <= {"ok", "warn"}
    assert self_check_exit(result) == 0
