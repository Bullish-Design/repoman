from repoman.registry import ACTIVITIES, DEFAULT_MANAGERS, REGISTRY, REMOVED_MANAGERS, SPINE, Manager


def test_keys_match_their_entry():
    for key, m in REGISTRY.items():
        assert m.key == key


def test_skill_defaults_to_command():
    # Manager.__post_init__ fills skill from command when omitted.
    assert Manager("x", "xcli", "core", "s").skill == "xcli"
    assert Manager("x", "xcli", "core", "s", skill="custom").skill == "custom"


def test_default_managers_are_registered():
    assert set(DEFAULT_MANAGERS) <= set(REGISTRY)


def test_tiers_are_known():
    assert {m.tier for m in REGISTRY.values()} <= {"core", "publish", "situational"}


def test_spine_keys_are_registered_or_none():
    for _label, key in SPINE:
        assert key is None or key in REGISTRY


def test_spine_is_three_ordered_phases():
    assert SPINE == (("change", None), ("verify", "test"), ("integrate", "git"))


def test_activities_are_unordered_and_outside_the_spine():
    assert ACTIVITIES == (("birth / converge", "copy"),)
    for _label, key in ACTIVITIES:
        assert key in REGISTRY
    spine_keys = {key for _label, key in SPINE}
    assert not spine_keys & {key for _label, key in ACTIVITIES}


def test_spine_has_no_save_or_scaffold_phase():
    # `save` is a deprecated gitman alias; scaffold happens before the repo exists.
    labels = {label for label, _key in (*SPINE, *ACTIVITIES)}
    assert not labels & {"save", "scaffold"}


def test_git_route_names_gitman_work_and_done():
    git = REGISTRY["git"]
    assert "gitman work" in git.route_when
    assert "gitman done" in git.route_when
    assert "jj" in git.route_when and "gh" in git.route_when
    for retired in ("land", "sync", "repair", "release", "undo"):
        assert retired not in git.route_when


def test_core_managers_present():
    assert {"copy", "git", "test"} <= set(REGISTRY)


def test_the_roster_is_exactly_copy_git_test():
    assert set(REGISTRY) == {"copy", "git", "test"}


def test_removed_managers_are_not_registered():
    # A removed key stays out of the registry. The doctor reports it instead.
    assert REMOVED_MANAGERS == {"doc": "0.13.0"}
    assert not set(REMOVED_MANAGERS) & set(REGISTRY)


def test_testee_has_a_minimum_version_and_copy_git_have_none():
    assert REGISTRY["test"].min_version == "0.6.0"
    assert REGISTRY["copy"].min_version == REGISTRY["git"].min_version == ""


def test_version_is_read_from_the_installed_distribution():
    # There is now ONE version: pyproject's, read back through importlib.metadata.
    # The old spelling kept a second copy in src/repoman/__init__.py and asserted the
    # two matched — which they did not, at release time, because nothing ran this test
    # before the tag. 0.7.4 shipped reporting "repoman 0.7.3".
    #
    # This still compares against pyproject, so an installed-but-stale environment is
    # caught; it just no longer has a hand-written literal to catch.
    import tomllib
    from pathlib import Path

    import repoman

    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with open(pyproject, "rb") as fh:
        declared = tomllib.load(fh)["project"]["version"]
    assert repoman.__version__ == declared
    # Assert the DERIVATION positively. An earlier spelling asserted the absence of
    # `__version__ = "`, which the fallback line matches — so the guard failed on
    # correct code, while a real literal could have sat right beside it.
    source = (Path(__file__).resolve().parents[1] / "src" / "repoman" / "__init__.py").read_text()
    assert 'version("repoman")' in source, "the version must be read from the installed distribution"
