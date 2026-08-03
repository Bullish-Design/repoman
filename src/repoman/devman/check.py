"""Skill-ownership lint for `repoman doctor` — tool-shipped / genome / overlay.

devman's static assets (the devenv-literacy skills, docs export, articles)
moved into the **genome** (template-py): they ship with the template and are
converged by ``copyroom update``, so RepoMan no longer installs static copies
and the ``.devman-source`` manifest is retired.

``repoman doctor`` now lints what is actually present under ``<skills_dir>/``
and classifies each skill by **ownership**:

* ``repoman/`` — the generated entrypoint router (Repoman owns it; produced by
  ``repoman install-skills`` at sync time);
* the copyroom canonical set (``copyroom``, ``copyroom-adopt``,
  ``copyroom-template-edit``) — **tool-shipped**: copyroom owns the content
  (package assets), materialized by ``copyroom agent-files export``; copyroom's
  own doctor checks currency;
* anything else — **genome** (template-converged, e.g. the ``devenv-*`` skills)
  or a repo **overlay** — reported as present, never judged (the two can't be
  distinguished statically).

All rows are ``warn``-level at most: a repo that hasn't adopted the convention
yet is reported, never fatal.
"""

from __future__ import annotations

from pathlib import Path

from ..checks import SelfCheck

#: The canonical skills copyroom ships (package assets under agent/assets/skills/).
CANONICAL_COPYROOM_SKILLS: tuple[str, ...] = (
    "copyroom",
    "copyroom-adopt",
    "copyroom-template-edit",
)

#: The generated entrypoint skill Repoman itself owns.
ENTRYPOINT_SKILL = "repoman"


def skill_ownership_checks(repo_root: str, skills_dir: str) -> list[SelfCheck]:
    """Lint skill ownership under ``<repo_root>/<skills_dir>/``.

    Returns one ``SelfCheck`` per ownership class:

    - ``skill:tool-shipped`` — the copyroom canonical set is present (warn when
      a canonical skill is missing → run ``copyroom agent-files export``);
    - ``skill:genome-overlay`` — non-canonical, non-entrypoint skills present,
      classified as genome-shipped or repo overlay (ok, informational).

    The entrypoint presence itself is covered by ``checks.run_self_check``
    (``skill:entrypoint``).
    """
    root = Path(repo_root)
    skills_root = root / skills_dir
    out: list[SelfCheck] = []

    if not skills_root.is_dir():
        out.append(
            SelfCheck(
                "skill:tool-shipped",
                "warn",
                f"{skills_dir} missing — run `copyroom agent-files export` + `repoman install-skills`",
            )
        )
        return out

    present = {
        p.name
        for p in skills_root.iterdir()
        if p.is_dir() and (p / "SKILL.md").is_file()
    }

    missing = [n for n in CANONICAL_COPYROOM_SKILLS if n not in present]
    out.append(
        SelfCheck(
            "skill:tool-shipped",
            "ok" if not missing else "warn",
            "canonical copyroom skills present"
            if not missing
            else f"missing {missing} — run `copyroom agent-files export`",
        )
    )

    others = sorted(present - {ENTRYPOINT_SKILL} - set(CANONICAL_COPYROOM_SKILLS))
    if others:
        out.append(
            SelfCheck(
                "skill:genome-overlay",
                "ok",
                "genome or overlay: " + ", ".join(others),
            )
        )

    return out
