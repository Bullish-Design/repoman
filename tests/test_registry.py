from repoman.registry import DEFAULT_MANAGERS, REGISTRY, SPINE, Manager


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


def test_core_managers_present():
    assert {"copy", "git", "test"} <= set(REGISTRY)


def test_agent_entry_shape():
    m = REGISTRY["agent"]
    assert m.command == "mypi"  # console script, not the dist name
    assert m.tier == "situational"
    assert m.doctor == ["doctor"] and m.status == ["paths"]
