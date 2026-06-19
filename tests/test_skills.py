from repoman.registry import REGISTRY
from repoman.skills import build_spine, install_entrypoint, render_entrypoint


def test_spine_only_enabled_plus_change():
    assert build_spine({"copy", "test"}) == "scaffold → change → verify"
    assert build_spine({"test"}) == "change → verify"
    assert build_spine({"copy", "git", "test"}) == "scaffold → change → verify → save"


def test_change_step_always_present():
    assert "change" in build_spine(set())


def test_render_only_names_enabled_managers():
    out = render_entrypoint([REGISTRY["copy"], REGISTRY["test"]], ".claude/skills")
    assert "copy test" in out               # managers line
    assert "copyroom" in out and "testee" in out
    assert "gitman" not in out              # not enabled → not routed
    assert "{{" not in out                  # StrictUndefined: nothing left unrendered
    assert ".claude/skills" in out


def test_install_writes_to_skills_dir(tmp_path):
    dest = install_entrypoint([REGISTRY["test"]], ".claude/skills", str(tmp_path))
    assert dest == tmp_path / ".claude/skills" / "repoman" / "SKILL.md"
    assert dest.read_text().startswith("---\nname: repoman")
