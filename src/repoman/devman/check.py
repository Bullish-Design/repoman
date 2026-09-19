"""Skill-link lint for `repoman doctor` — expected links vs genome/overlay.

The central devman overlay at ``~/.config/devman`` owns ``.agents/`` in every
repo (PLATFORM-INVESTIGATION §3.3 R3). A fleet skill is a **relative symlink** in
the project's central directory:

    ~/.config/devman/projects/<p>/agents/skills/<name> -> ../../../../skills/<name>

Real entries are only project-specific skills and the generated router. No repo
tracks agent skills. Two writers remain, on disjoint paths: devman curates the
pool links; ``repoman install-skills`` generates ``<p>/SKILL.md``.

``repoman doctor`` reads what is present under ``<skills_dir>/`` and classifies
each entry:

* ``repoman/`` — the generated entrypoint router (Repoman owns it; produced by
  ``repoman install-skills`` at sync time);
* the expected link set (:data:`EXPECTED_SKILLS`) — the four manager skills the
  router needs, the copyroom canonical set, and the personal layer;
* anything else — a **project-specific** skill or a repo **overlay** — reported
  as present, never judged (the two can't be distinguished statically).

A missing expected link is ``warn``, never ``fail``. The agent surface is
developer guidance, not an input to evaluating or verifying a clone (§3.2), so it
must not fail a gate: a fresh clone and a CI runner legitimately have no links,
and a fatal row would make them fail. ``fail`` stays reserved for broken wiring
(exit 2 in the ``0/1/2/3`` contract in :mod:`repoman.checks`).
"""

from __future__ import annotations

from pathlib import Path

from ..checks import SelfCheck

#: The four manager skills the generated router needs. ``skills.py`` emits a
#: routing row only for a manager whose ``<skills_dir>/<command>/SKILL.md``
#: resolves, and ``m.skill`` defaults to ``m.command``.
MANAGER_SKILLS: tuple[str, ...] = ("copyroom", "gitman", "testee", "docman")

#: The copyroom canonical set: the tool's entrypoint and its two sub-skills.
CANONICAL_COPYROOM_SKILLS: tuple[str, ...] = (
    "copyroom",
    "copyroom-adopt",
    "copyroom-template-edit",
)

#: The personal layer the global ``CLAUDE.md`` points at.
PERSONAL_LAYER_SKILLS: tuple[str, ...] = ("my-ai", "writing")

#: The full expected link set for a managed project — the four manager skills
#: plus the canonical set plus the personal layer (``copyroom`` appears once).
EXPECTED_SKILLS: tuple[str, ...] = tuple(
    sorted(set(MANAGER_SKILLS) | set(CANONICAL_COPYROOM_SKILLS) | set(PERSONAL_LAYER_SKILLS))
)

#: The generated entrypoint skill Repoman itself owns.
ENTRYPOINT_SKILL = "repoman"


def skill_ownership_checks(repo_root: str, skills_dir: str) -> list[SelfCheck]:
    """Lint the skill links under ``<repo_root>/<skills_dir>/``.

    Returns one ``SelfCheck`` per class:

    - ``skill:tool-shipped`` — every skill in the expected link set resolves
      (warn when one is missing → add a relative pool link in the central dir);
    - ``skill:genome-overlay`` — non-expected, non-entrypoint skills present,
      classified as project-specific or overlay (ok, informational).

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
                f"{skills_dir} missing — link the devman pool skills into the project's "
                "central dir, then run `repoman install-skills`",
            )
        )
        return out

    # ``is_dir``/``is_file`` follow symlinks, so a relative pool link registers as
    # present exactly when its target resolves. A dangling link does not.
    try:
        present = {p.name for p in skills_root.iterdir() if p.is_dir() and (p / "SKILL.md").is_file()}
    except OSError as exc:
        # The lint is a diagnostic; an unreadable skills dir is a finding, not a crash.
        return [SelfCheck("skill:tool-shipped", "warn", f"{skills_dir} unreadable: {exc.strerror or exc}")]

    missing = [n for n in EXPECTED_SKILLS if n not in present]
    out.append(
        SelfCheck(
            "skill:tool-shipped",
            "ok" if not missing else "warn",
            "expected pool links present"
            if not missing
            else f"missing {missing} — add the pool link(s): ln -s ../../../../skills/<name> "
            "~/.config/devman/projects/<project>/agents/skills/<name>",
        )
    )

    others = sorted(present - {ENTRYPOINT_SKILL} - set(EXPECTED_SKILLS))
    if others:
        out.append(
            SelfCheck(
                "skill:genome-overlay",
                "ok",
                "project-specific or overlay: " + ", ".join(others),
            )
        )

    return out
