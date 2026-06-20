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


def test_session_entry_shape():
    m = REGISTRY["session"]
    assert m.command == "zelligate"
    assert m.tier == "situational"
    assert m.doctor == ["doctor"] and m.status == ["list"]


def test_agent_entry_shape():
    m = REGISTRY["agent"]
    assert m.command == "mypi"  # console script, not the dist name
    assert m.tier == "situational"
    assert m.doctor == ["doctor"] and m.status == ["paths"]


def test_doc_entry_shape():
    m = REGISTRY["doc"]
    assert m.command == "docman"
    assert m.tier == "publish"
    assert m.doctor == ["doctor"]
    assert m.status is None  # docman has no status verb — repoman status skips it
    assert m.skill == "docman"  # defaults to the command; docman ships a `docman` skill dir


def test_spec_command_is_not_the_thirdparty_binary():
    # Regression guard: `spec` must invoke the family manager CLI (`alliman`), NOT the
    # third-party juxt/allium-tools `allium` binary, which has no `doctor` verb.
    m = REGISTRY["spec"]
    assert m.command == "alliman"  # NOT "allium"
    assert m.tier == "situational" and m.status is None
    assert m.doctor == ["doctor"]
    # allium-env installs its manager skill as `allium-entrypoint`, not `alliman`.
    assert m.skill == "allium-entrypoint"
