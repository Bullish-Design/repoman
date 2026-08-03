"""Tests for repoman's skill-ownership lint (devman/check.py).

devman's static assets moved into the genome (template-py); RepoMan's only
remaining devman role is classifying what's under `.agents/skills/` by
ownership: tool-shipped (copyroom canonical set) vs genome-or-overlay.
"""

from __future__ import annotations

from repoman.devman.check import CANONICAL_COPYROOM_SKILLS, skill_ownership_checks


def _names(result):
    return {c.name: c for c in result}


def test_warns_when_skills_dir_missing(tmp_path):
    result = skill_ownership_checks(str(tmp_path), ".agents/skills")
    names = _names(result)
    assert names["skill:tool-shipped"].level == "warn"
    assert "copyroom agent-files export" in names["skill:tool-shipped"].detail


def test_warns_when_canonical_skill_missing(tmp_path):
    skills = tmp_path / ".agents/skills"
    (skills / "repoman").mkdir(parents=True)
    (skills / "repoman" / "SKILL.md").write_text("---\nname: repoman\n---\n")
    result = skill_ownership_checks(str(tmp_path), ".agents/skills")
    names = _names(result)
    assert names["skill:tool-shipped"].level == "warn"
    for name in CANONICAL_COPYROOM_SKILLS:
        assert name in names["skill:tool-shipped"].detail


def test_ok_when_canonical_set_present(tmp_path):
    skills = tmp_path / ".agents/skills"
    for name in (*CANONICAL_COPYROOM_SKILLS, "repoman"):
        skill = skills / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(f"---\nname: {name}\n---\n")
    result = skill_ownership_checks(str(tmp_path), ".agents/skills")
    names = _names(result)
    assert names["skill:tool-shipped"].level == "ok"


def test_genome_overlay_skills_reported_present(tmp_path):
    skills = tmp_path / ".agents/skills"
    for name in (*CANONICAL_COPYROOM_SKILLS, "devenv-run-commands", "repo-local"):
        skill = skills / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("# skill\n")
    result = skill_ownership_checks(str(tmp_path), ".agents/skills")
    names = _names(result)
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
