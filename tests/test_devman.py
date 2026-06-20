import repoman.devman.assets as assets
import repoman.devman.install as install_mod
from repoman.devman.assets import expected_articles, expected_docs, expected_skills
from repoman.devman.install import MANIFEST, install_devman


def test_expected_skills_non_empty():
    # Guards the package-data globs: if assets don't ship, the self-check is blind.
    skills = expected_skills()
    assert skills, "devman ships no skills — package-data or scaffold is broken"
    assert "devenv-run-commands" in skills


def test_expected_docs_and_articles_present():
    assert "lock-and-cache.md" in expected_docs()
    assert "the-lock-cache-loop.md" in expected_articles()


def test_install_writes_every_skill(tmp_path):
    written = install_devman(".claude/skills", ".agents/devenv", str(tmp_path))
    for name in expected_skills():
        skill = tmp_path / ".claude/skills" / name / "SKILL.md"
        assert skill.exists()
        assert skill in written


def test_install_writes_docs_and_articles(tmp_path):
    install_devman(".claude/skills", ".agents/devenv", str(tmp_path))
    for name in expected_docs():
        assert (tmp_path / ".agents/devenv" / name).exists()
    for name in expected_articles():
        assert (tmp_path / ".agents/devenv/articles" / name).exists()


def test_install_writes_manifest_with_version(tmp_path):
    install_devman(".claude/skills", ".agents/devenv", str(tmp_path))
    manifest = tmp_path / ".claude/skills" / MANIFEST
    assert manifest.exists()
    text = manifest.read_text()
    assert "repoman version:" in text
    assert "devenv-run-commands" in text


def test_install_is_idempotent(tmp_path):
    first = install_devman(".claude/skills", ".agents/devenv", str(tmp_path))
    second = install_devman(".claude/skills", ".agents/devenv", str(tmp_path))
    assert first == second


def test_enumerators_tolerate_missing_dirs(tmp_path, monkeypatch):
    # Defensive branch: if a shipped asset dir is absent, enumeration returns [] (no crash).
    missing = tmp_path / "nope"
    monkeypatch.setattr(assets, "SKILLS_SRC", missing)
    monkeypatch.setattr(assets, "DOCS_SRC", missing)
    monkeypatch.setattr(assets, "ARTICLES_SRC", missing)
    assert expected_skills() == []
    assert expected_docs() == []
    assert expected_articles() == []


def test_install_skips_missing_articles_dir(tmp_path, monkeypatch):
    # If articles aren't shipped, install still writes skills + a manifest without erroring.
    monkeypatch.setattr(install_mod, "ARTICLES_SRC", tmp_path / "nope")
    written = install_devman(".claude/skills", ".agents/devenv", str(tmp_path))
    assert (tmp_path / ".claude/skills" / MANIFEST) in written
    assert not (tmp_path / ".agents/devenv/articles").exists()
