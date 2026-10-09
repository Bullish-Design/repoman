"""Generate the RepoMan entrypoint (router) skill.

Pass-through means each manager keeps its own skill. RepoMan adds ONE generated
entrypoint skill above them — the single "start here" that owns the lifecycle order
and routes to each manager's own skill. The header reflects the enabled roster; the
routing table names only manager skills that are present on disk. Single source of
truth: the same manager list the nix module and CLI read.
"""

from __future__ import annotations

import os
from pathlib import Path

from jinja2 import Environment, StrictUndefined

from .registry import ACTIVITIES, SPINE, Manager

_TEMPLATE = Path(__file__).parent / "templates" / "entrypoint.SKILL.md.j2"

#: Position of each manager in the table order. Spine managers come first, in spine
#: order. Activity managers follow, in `ACTIVITIES` order. The routing table uses this
#: order, not the order of `REPOMAN_MANAGERS`.
_ORDER = {key: i for i, key in enumerate(k for _label, k in (*SPINE, *ACTIVITIES) if k is not None)}


class SkillsDirError(ValueError):
    """`skills_dir` is not a repo-relative directory."""


def resolve_skills_dir(skills_dir: str, repo_root: str) -> Path:
    """``<repo_root>/<skills_dir>``, refusing anything that escapes the repo.

    ``skills_dir`` comes from ``REPOMAN_SKILLS_DIR``; an absolute value silently
    made ``Path(repo_root) / skills_dir`` resolve to the absolute path alone, so
    `install-skills` would write outside the repo.
    """

    candidate = Path(skills_dir)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise SkillsDirError(
            f"skills dir must be relative to the repo root, got {skills_dir!r} "
            "(set REPOMAN_SKILLS_DIR to something like '.agents/skills')"
        )
    return Path(repo_root) / candidate


def _enabled_labels(entries: tuple[tuple[str, str | None], ...], enabled_keys: set[str]) -> list[str]:
    return [label for label, key in entries if key is None or key in enabled_keys]


def build_spine(enabled_keys: set[str]) -> str:
    """Assemble the ordered phases from only the enabled managers."""

    return " → ".join(_enabled_labels(SPINE, enabled_keys))


def build_activities(enabled_keys: set[str]) -> str:
    """Assemble the unordered activities from only the enabled managers."""

    return " · ".join(_enabled_labels(ACTIVITIES, enabled_keys))


def _ordered(managers: list[Manager]) -> list[Manager]:
    """Roster in table order: spine managers, then activity managers, then the rest.

    A manager outside both lists keeps its relative order.
    """

    return sorted(
        managers,
        key=lambda m: (_ORDER.get(m.key, len(_ORDER)), managers.index(m)),
    )


def render_entrypoint(
    managers: list[Manager],
    skills_dir: str,
    repo_root: str,
    *,
    skills_root: Path | None = None,
) -> str:
    """Render the entrypoint skill markdown for the enabled managers."""

    ordered = _ordered(managers)
    skills_root = skills_root or resolve_skills_dir(skills_dir, repo_root)
    present = [m for m in ordered if (skills_root / m.skill / "SKILL.md").is_file()]
    env = Environment(undefined=StrictUndefined, keep_trailing_newline=True, trim_blocks=True, lstrip_blocks=True)
    template = env.from_string(_TEMPLATE.read_text(encoding="utf-8"))
    enabled = {m.key for m in ordered}
    return template.render(
        managers=" ".join(m.key for m in ordered),
        spine=build_spine(enabled),
        activities=build_activities(enabled),
        gitman_v2=any(m.key == "git" and m.skill == "gitman-v2" for m in ordered),
        has_test="test" in enabled,
        rows=[{"key": m.key, "command": m.command, "skill": m.skill, "when": m.route_when} for m in present],
        skills_dir=skills_dir,
    )


def install_entrypoint(managers: list[Manager], skills_dir: str, repo_root: str) -> Path:
    """Write the entrypoint skill to ``<repo_root>/<skills_dir>/repoman/SKILL.md``.

    Written via a temp file + atomic replace: a partial write would leave a
    truncated SKILL.md that the next `doctor` happily reports as present.
    """

    dest = resolve_skills_dir(skills_dir, repo_root) / "repoman" / "SKILL.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    content = render_entrypoint(managers, skills_dir, repo_root, skills_root=dest.parent.parent)
    tmp = dest.with_name(dest.name + ".tmp")
    try:
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, dest)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise
    return dest
