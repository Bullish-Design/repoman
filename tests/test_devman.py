"""Tests for RepoMan's agent-surface link lint.

The central devman overlay owns `.agents/`. This namespace classifies what is
under `.agents/skills/`: the expected pool-link set vs project-specific or
overlay skills.
"""

from __future__ import annotations

import os

from repoman.devman.check import (
    CANONICAL_COPYROOM_SKILLS,
    EXPECTED_SKILLS,
    MANAGER_SKILLS,
    PERSONAL_LAYER_SKILLS,
    skill_ownership_checks,
)


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


def test_expected_set_covers_managers_canonical_and_personal():
    assert set(MANAGER_SKILLS) <= set(EXPECTED_SKILLS)
    assert set(CANONICAL_COPYROOM_SKILLS) <= set(EXPECTED_SKILLS)
    assert set(PERSONAL_LAYER_SKILLS) <= set(EXPECTED_SKILLS)
    assert len(EXPECTED_SKILLS) == len(set(EXPECTED_SKILLS))


def test_warns_when_skills_dir_missing(tmp_path):
    result = skill_ownership_checks(str(tmp_path), ".agents/skills")
    row = _names(result)["skill:tool-shipped"]
    assert row.level == "warn"
    assert "pool" in row.detail
    # The old remediation named copyroom's deleted export surface.
    assert "copyroom agent-files export" not in row.detail


def test_warns_when_a_manager_link_is_missing(tmp_path):
    repo, skills, _pool = _layout(tmp_path)
    for name in EXPECTED_SKILLS:
        if name != "gitman":
            _real_skill(skills, name)
    row = _names(skill_ownership_checks(str(repo), ".agents/skills"))["skill:tool-shipped"]
    assert row.level == "warn"
    assert "gitman" in row.detail
    assert "ln -s" in row.detail


def test_symlinked_pool_skills_register_as_present(tmp_path):
    repo, skills, pool = _layout(tmp_path)
    for name in EXPECTED_SKILLS:
        _link_pool_skill(pool, skills, name)
    assert _names(skill_ownership_checks(str(repo), ".agents/skills"))["skill:tool-shipped"].level == "ok"


def test_dangling_pool_link_does_not_register(tmp_path):
    repo, skills, _pool = _layout(tmp_path)
    for name in EXPECTED_SKILLS:
        if name == "gitman":
            os.symlink("../../../../skills/gitman", skills / name)
            continue
        _real_skill(skills, name)
    assert _names(skill_ownership_checks(str(repo), ".agents/skills"))["skill:tool-shipped"].level == "warn"


def test_project_specific_skills_reported_present(tmp_path):
    repo, skills, _pool = _layout(tmp_path)
    for name in (*EXPECTED_SKILLS, "devenv-run-commands", "repo-local"):
        _real_skill(skills, name)
    names = _names(skill_ownership_checks(str(repo), ".agents/skills"))
    assert names["skill:tool-shipped"].level == "ok"
    row = names["skill:genome-overlay"]
    assert row.level == "ok"
    assert "devenv-run-commands" in row.detail
    assert "repo-local" in row.detail
    # The entrypoint is RepoMan's own — never classified as genome/overlay.
    assert "repoman" not in row.detail


def test_warn_is_non_fatal(tmp_path):
    result = skill_ownership_checks(str(tmp_path), ".agents/skills")
    from repoman.checks import self_check_exit

    assert self_check_exit(result) == 0
