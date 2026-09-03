"""Generate the RepoMan entrypoint (router) skill.

Pass-through means each manager keeps its own skill. RepoMan adds ONE generated
entrypoint skill above them — the single "start here" that owns the lifecycle order
and routes to each manager's own skill. It is rendered from the enabled roster, so
it only ever names installed managers (no dangling routes). Single source of truth:
the same manager list the nix module and CLI read.
"""

from __future__ import annotations

import os
from pathlib import Path

from jinja2 import Environment, StrictUndefined

from .registry import SPINE, Manager

_TEMPLATE = Path(__file__).parent / "templates" / "entrypoint.SKILL.md.j2"

#: Position of each manager in the canonical lifecycle. The routing table follows the
#: same order as the spine printed above it, rather than whatever order the roster
#: happened to be written in `REPOMAN_MANAGERS`.
_SPINE_ORDER = {key: i for i, (_label, key) in enumerate(SPINE) if key is not None}


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


def build_spine(enabled_keys: set[str]) -> str:
    """Assemble the lifecycle spine from only the enabled managers."""

    steps = [label for label, key in SPINE if key is None or key in enabled_keys]
    return " → ".join(steps)


def _ordered(managers: list[Manager]) -> list[Manager]:
    """Roster in lifecycle order; managers outside the spine keep their relative order."""

    return sorted(
        managers,
        key=lambda m: (_SPINE_ORDER.get(m.key, len(_SPINE_ORDER)), managers.index(m)),
    )


def render_entrypoint(managers: list[Manager], skills_dir: str) -> str:
    """Render the entrypoint skill markdown for the enabled managers."""

    ordered = _ordered(managers)
    env = Environment(undefined=StrictUndefined, keep_trailing_newline=True)
    template = env.from_string(_TEMPLATE.read_text(encoding="utf-8"))
    return template.render(
        managers=" ".join(m.key for m in ordered),
        spine=build_spine({m.key for m in ordered}),
        rows=[{"key": m.key, "command": m.command, "skill": m.skill, "when": m.route_when} for m in ordered],
        skills_dir=skills_dir,
    )


def install_entrypoint(managers: list[Manager], skills_dir: str, repo_root: str) -> Path:
    """Write the entrypoint skill to ``<repo_root>/<skills_dir>/repoman/SKILL.md``.

    Written via a temp file + atomic replace: a partial write would leave a
    truncated SKILL.md that the next `doctor` happily reports as present.
    """

    dest = resolve_skills_dir(skills_dir, repo_root) / "repoman" / "SKILL.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    content = render_entrypoint(managers, skills_dir)
    tmp = dest.with_name(dest.name + ".tmp")
    try:
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, dest)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise
    return dest
