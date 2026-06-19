"""Generate the RepoMan entrypoint (router) skill.

Pass-through means each manager keeps its own skill. RepoMan adds ONE generated
entrypoint skill above them — the single "start here" that owns the lifecycle order
and routes to each manager's own skill. It is rendered from the enabled roster, so
it only ever names installed managers (no dangling routes). Single source of truth:
the same manager list the nix module and CLI read.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, StrictUndefined

from .registry import SPINE, Manager

_TEMPLATE = Path(__file__).parent / "templates" / "entrypoint.SKILL.md.j2"


def build_spine(enabled_keys: set[str]) -> str:
    """Assemble the lifecycle spine from only the enabled managers."""

    steps = [label for label, key in SPINE if key is None or key in enabled_keys]
    return " → ".join(steps)


def render_entrypoint(managers: list[Manager], skills_dir: str) -> str:
    """Render the entrypoint skill markdown for the enabled managers."""

    env = Environment(undefined=StrictUndefined, keep_trailing_newline=True)
    template = env.from_string(_TEMPLATE.read_text())
    return template.render(
        managers=" ".join(m.key for m in managers),
        spine=build_spine({m.key for m in managers}),
        rows=[
            {"key": m.key, "command": m.command, "skill": m.skill, "when": m.route_when}
            for m in managers
        ],
        skills_dir=skills_dir,
    )


def install_entrypoint(managers: list[Manager], skills_dir: str, repo_root: str) -> Path:
    """Write the entrypoint skill to ``<repo_root>/<skills_dir>/repoman/SKILL.md``."""

    dest = Path(repo_root) / skills_dir / "repoman" / "SKILL.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(render_entrypoint(managers, skills_dir))
    return dest
