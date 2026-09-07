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


def test_install_model_split():
    # project 12: pure-CLI managers are toolchain-installed; testee is uv-declared.
    for key in ("copy", "git", "doc"):
        assert REGISTRY[key].install == "toolchain"
    assert REGISTRY["test"].install == "uv"


def test_package_defaults_to_command():
    # the distribution name the uv:<key> check looks for in pyproject.toml.
    assert Manager("x", "xcli", "core", "s").package == "xcli"
    for key, m in REGISTRY.items():
        assert m.package == m.command


def test_install_model_is_validated():
    # a typo in install must fail loudly, never silently disable a doctor check.
    import pytest

    with pytest.raises(ValueError):
        Manager("x", "xcli", "core", "s", install="bogus")
    Manager("x", "xcli", "core", "s", install="toolchain")
    Manager("x", "xcli", "core", "s", install="uv")


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
