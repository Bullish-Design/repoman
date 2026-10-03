from repoman.registry import REGISTRY
from repoman.skills import build_activities, build_spine, install_entrypoint, render_entrypoint


def test_spine_renders_exactly_the_enabled_phases():
    assert build_spine({"git", "test"}) == "change → verify → integrate"
    assert build_spine({"test"}) == "change → verify"
    assert build_spine({"git"}) == "change → integrate"


def test_spine_ignores_activity_managers():
    assert build_spine({"copy", "doc"}) == "change"
    assert build_spine({"copy", "git", "test", "doc"}) == "change → verify → integrate"


def test_change_phase_always_present():
    assert build_spine(set()) == "change"


def test_roster_without_test_or_git_still_renders_change(tmp_path):
    out = render_entrypoint([REGISTRY["copy"], REGISTRY["doc"]], ".agents/skills", str(tmp_path))
    assert "```\nchange\n```" in out
    assert "verify →" not in out and "→ integrate" not in out
    assert "{{" not in out


def test_activities_render_only_the_enabled_ones_in_declared_order():
    assert build_activities({"doc", "copy"}) == "birth / converge · docs"
    assert build_activities({"doc"}) == "docs"
    assert build_activities({"test", "git"}) == ""
    assert build_activities(set()) == ""


def test_activities_render_apart_from_the_phases(tmp_path):
    roster = [REGISTRY["doc"], REGISTRY["git"], REGISTRY["copy"], REGISTRY["test"]]
    out = render_entrypoint(roster, ".agents/skills", str(tmp_path))
    assert "change → verify → integrate" in out
    assert "birth / converge · docs" in out
    assert "→ birth" not in out and "→ docs" not in out
    assert "## Activities" in out
    assert out.index("change → verify → integrate") < out.index("## Activities")


def test_activities_section_is_absent_without_activity_managers(tmp_path):
    out = render_entrypoint([REGISTRY["git"], REGISTRY["test"]], ".agents/skills", str(tmp_path))
    assert "## Activities" not in out


def test_laws_name_land_and_never_save():
    out = render_entrypoint([REGISTRY["test"]], ".agents/skills", "/nonexistent")
    laws = out.split("## Laws")[1]
    assert "Verify before you integrate" in laws
    assert "Never integrate on red" in laws
    assert "land" in laws
    assert "save" not in out


def test_render_has_no_doubled_blank_lines(tmp_path):
    for key in ("copy", "git", "test", "doc"):
        skill = tmp_path / ".agents/skills" / REGISTRY[key].skill / "SKILL.md"
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_text(f"---\nname: {key}\n---\n")
    roster = [REGISTRY[k] for k in ("copy", "git", "test", "doc")]
    for r in (roster, [REGISTRY["test"]], []):
        out = render_entrypoint(r, ".agents/skills", str(tmp_path))
        assert "\n\n\n" not in out


def test_render_only_names_enabled_managers(tmp_path):
    for key in ("copy", "test"):
        skill = tmp_path / ".claude/skills" / REGISTRY[key].skill / "SKILL.md"
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_text(f"---\nname: {key}\n---\n")
    out = render_entrypoint([REGISTRY["copy"], REGISTRY["test"]], ".claude/skills", str(tmp_path))
    assert "test copy" in out  # managers line, spine manager first
    assert "copyroom" in out and "testee" in out
    assert "gitman" not in out  # not enabled → not routed
    assert "{{" not in out  # StrictUndefined: nothing left unrendered
    assert ".claude/skills" in out


def test_install_writes_to_skills_dir(tmp_path):
    dest = install_entrypoint([REGISTRY["test"]], ".claude/skills", str(tmp_path))
    assert dest == tmp_path / ".claude/skills" / "repoman" / "SKILL.md"
    assert dest.read_text().startswith("---\nname: repoman")


def test_routing_table_follows_the_lifecycle_spine_not_the_env_order(tmp_path):
    # The spine above the table is canonical; the table under it must not reorder
    # itself just because REPOMAN_MANAGERS was written in a different order.
    roster = [REGISTRY["git"], REGISTRY["copy"], REGISTRY["test"]]
    for key in ("copy", "git", "test"):
        skill = tmp_path / ".agents/skills" / REGISTRY[key].skill / "SKILL.md"
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_text(f"---\nname: {key}\n---\n")
    out = render_entrypoint(roster, ".agents/skills", str(tmp_path))
    rows = [line for line in out.splitlines() if line.startswith("| ") and "`" in line]
    # spine managers in spine order, then activity managers
    assert [r.split("|")[2].strip() for r in rows] == ["test", "git", "copy"]
    assert "change → verify → integrate" in out
    assert "**test git copy**" in out  # the managers line follows the same order


def test_install_is_atomic_and_leaves_no_temp_file(tmp_path):
    dest = install_entrypoint([REGISTRY["test"]], ".agents/skills", str(tmp_path))
    assert dest.exists()
    assert not dest.with_name(dest.name + ".tmp").exists()


def test_install_overwrites_cleanly_on_reinstall(tmp_path):
    skill = tmp_path / ".agents/skills/testee/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: testee\n---\n")
    install_entrypoint([REGISTRY["copy"], REGISTRY["test"]], ".agents/skills", str(tmp_path))
    dest = install_entrypoint([REGISTRY["test"]], ".agents/skills", str(tmp_path))
    text = dest.read_text()
    assert "copyroom" not in text  # no leftovers from the wider roster
    assert "testee" in text


def test_render_filters_routes_to_skills_present_on_disk(tmp_path):
    skill = tmp_path / ".agents/skills/testee/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: testee\n---\n")
    out = render_entrypoint([REGISTRY["copy"], REGISTRY["test"]], ".agents/skills", str(tmp_path))
    assert "**test copy**" in out
    assert "| test |" in out
    assert "| copy |" not in out
    assert "For domain detail" in out


def test_render_omits_footer_when_no_manager_skill_is_present(tmp_path):
    out = render_entrypoint([REGISTRY["copy"]], ".agents/skills", str(tmp_path))
    assert "**copy**" in out
    assert "| copy |" not in out
    assert "For domain detail" not in out


def test_resolve_skills_dir_rejects_escapes(tmp_path):
    import pytest

    from repoman.skills import SkillsDirError, resolve_skills_dir

    assert resolve_skills_dir(".agents/skills", str(tmp_path)) == tmp_path / ".agents/skills"
    with pytest.raises(SkillsDirError):
        resolve_skills_dir("/etc/skills", str(tmp_path))
    with pytest.raises(SkillsDirError):
        resolve_skills_dir("../../skills", str(tmp_path))


def test_install_cleans_up_its_temp_file_when_the_write_fails(tmp_path):
    import pytest

    skills = tmp_path / ".agents/skills" / "repoman"
    skills.mkdir(parents=True)
    skills.chmod(0o500)  # readable + executable, not writable
    try:
        with pytest.raises(OSError):
            install_entrypoint([REGISTRY["test"]], ".agents/skills", str(tmp_path))
        assert not (skills / "SKILL.md.tmp").exists()
    finally:
        skills.chmod(0o755)
