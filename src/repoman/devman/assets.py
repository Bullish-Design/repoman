"""Locate devman's shipped assets and the names that must end up installed.

The expected skill/doc set is derived from the *shipped package*, so the self-check
always knows what should be installed regardless of the consumer's state. Resolution
works for editable installs (working tree) and wheels (package-data) alike.
"""

from __future__ import annotations

from pathlib import Path

ASSETS = Path(__file__).parent / "assets"
SKILLS_SRC = ASSETS / "skills"
DOCS_SRC = ASSETS / "docs"
ARTICLES_SRC = ASSETS / "articles"


def expected_skills() -> list[str]:
    """Skill directory names devman ships (each has a SKILL.md)."""

    if not SKILLS_SRC.is_dir():
        return []
    return sorted(p.name for p in SKILLS_SRC.iterdir() if (p / "SKILL.md").exists())


def expected_docs() -> list[str]:
    """Doc filenames devman ships (the distilled docs export, not the articles)."""

    if not DOCS_SRC.is_dir():
        return []
    return sorted(p.name for p in DOCS_SRC.glob("*.md"))


def expected_articles() -> list[str]:
    """Article filenames devman ships (longer why + worked-example pieces)."""

    if not ARTICLES_SRC.is_dir():
        return []
    return sorted(p.name for p in ARTICLES_SRC.glob("*.md"))
