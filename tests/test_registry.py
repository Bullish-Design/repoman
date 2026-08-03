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


def test_doc_entry_shape():
    m = REGISTRY["doc"]
    assert m.command == "docman"
    assert m.tier == "publish"
    assert m.doctor == ["doctor"]
    assert m.status is None  # docman has no status verb — repoman status skips it
    assert m.skill == "docman"  # defaults to the command; docman ships a `docman` skill dir


def test_approach_b_managers_declare_their_nix_input():
    # The one remaining approach-B manager needs a presence-gated devenv.yaml input;
    # `repoman doctor` warns (provisioned:<key>) when it's missing.
    assert REGISTRY["doc"].nix_input == "docman"


def test_approach_a_and_pure_python_managers_have_no_nix_input():
    # Approach-A (copy) and pure-Python (test) + git need no consumer input.
    for key in ("copy", "git", "test"):
        assert REGISTRY[key].nix_input == ""
