"""Skill-link lint for `repoman doctor` — expected links vs genome/overlay.

The central devman overlay at ``~/.config/devman`` owns ``.agents/`` in every
repo (PLATFORM-INVESTIGATION §3.3 R3). A fleet skill is a **relative symlink** in
the project's central directory:

    ~/.config/devman/projects/<p>/agents/skills/<name> -> ../../../../skills/<name>

Real entries are only project-specific skills and the generated router. No repo
tracks agent skills. Two writers remain, on disjoint paths. A person curates the
pool links by hand in the central config repository; ``devman-link reconcile``
creates none of them. ``repoman install-skills`` generates
``<skills_dir>/repoman/SKILL.md``.

``repoman doctor`` reads what is present under ``<skills_dir>/`` and classifies
each entry:

* ``repoman/`` — the generated entrypoint router (Repoman owns it; produced by
  ``repoman install-skills`` at sync time);
* the expected link set (:func:`expected_skills`) — RepoMan's own policy,
  derived from the enabled roster: ``writing`` always, the skill of each enabled
  manager, and the two copyroom sub-skills when ``copy`` is enabled;
* anything else — a **project-specific** skill or a repo **overlay** — reported
  as present, never judged (the two can't be distinguished statically).

The expected link set is **RepoMan's own policy**, not a devman publication.
Devman publishes only one universal skill: ``UNIVERSAL_SKILLS = ("writing",)``
in ``devman/src/devman/doctor.py``. Its comment refuses to make ``gitman`` and
``copyroom`` universal. A repo expects a manager skill only when it enables that
manager, so a ``git``-only repo gets no warning for ``copyroom``, ``testee`` or
``docman``.

A missing expected link is ``warn``, never ``fail``. The agent surface is
developer guidance, not an input to evaluating or verifying a clone (§3.2), so it
must not fail a gate: a fresh clone and a CI runner legitimately have no links,
and a fatal row would make them fail. ``fail`` stays reserved for broken wiring
(exit 2 in the ``0/1/2/3`` contract in :mod:`repoman.checks`).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

from ..checks import SelfCheck
from ..registry import REGISTRY

#: Devman's one universal skill. Every repo expects it, whatever the roster.
UNIVERSAL_SKILLS: tuple[str, ...] = ("writing",)

#: Copyroom's canonical sub-skills. A repo expects them only when ``copy`` is enabled.
COPYROOM_SUB_SKILLS: tuple[str, ...] = ("copyroom-adopt", "copyroom-template-edit")

#: The generated entrypoint skill Repoman itself owns.
ENTRYPOINT_SKILL = "repoman"


def expected_skills(enabled: Iterable[str]) -> tuple[str, ...]:
    """Return the sorted skill names a repo with this roster expects.

    ``enabled`` holds manager keys (``copy``, ``git``, ``test``, ``doc``). The
    skill name of each key comes from :data:`repoman.registry.REGISTRY`. An
    unknown key adds nothing.
    """
    keys = set(enabled)
    names = set(UNIVERSAL_SKILLS)
    names.update(m.skill for k, m in REGISTRY.items() if k in keys)
    if "copy" in keys:
        names.update(COPYROOM_SUB_SKILLS)
    return tuple(sorted(names))


def skill_ownership_checks(repo_root: Path | str, skills_dir: str, enabled: Sequence[str]) -> list[SelfCheck]:
    """Lint the skill links under ``<repo_root>/<skills_dir>/``.

    ``enabled`` is the roster of manager keys. It decides the expected set (see
    :func:`expected_skills`). Rows are ``ok`` or ``warn``, never ``fail``: a clone
    or a CI checkout has no links, and a missing link must not gate.

    Returns one ``SelfCheck`` per class:

    - ``skill:tool-shipped`` — every skill in the expected set resolves
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

    expected = expected_skills(enabled)
    missing = [n for n in expected if n not in present]
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

    others = sorted(present - {ENTRYPOINT_SKILL} - set(expected))
    if others:
        out.append(
            SelfCheck(
                "skill:genome-overlay",
                "ok",
                "project-specific or overlay: " + ", ".join(others),
            )
        )

    return out
