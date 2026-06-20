"""devman self-checks for `repoman doctor` — are the literacy assets installed + current?

Reuses :class:`repoman.checks.SelfCheck` so the output and exit math stay uniform with the rest
of the preflight. devman stays **warn**-only for now (it is not yet mandatory); flip the levels
to ``fail`` once the literacy layer is required.
"""

from __future__ import annotations

from importlib.metadata import version
from pathlib import Path

from ..checks import SelfCheck
from .assets import expected_docs, expected_skills
from .install import MANIFEST


def devman_checks(repo_root: str, skills_dir: str, docs_dir: str) -> list[SelfCheck]:
    """Are devman's skills + docs installed in this repo, and at the current version?"""

    root = Path(repo_root)
    out: list[SelfCheck] = []

    missing_skills = [n for n in expected_skills() if not (root / skills_dir / n / "SKILL.md").exists()]
    out.append(
        SelfCheck(
            "devman:skills",
            "ok" if not missing_skills else "warn",
            "all installed" if not missing_skills else f"missing {missing_skills} — run `repoman install-skills`",
        )
    )

    missing_docs = [n for n in expected_docs() if not (root / docs_dir / n).exists()]
    out.append(
        SelfCheck(
            "devman:docs",
            "ok" if not missing_docs else "warn",
            docs_dir if not missing_docs else f"missing {len(missing_docs)} doc(s) — run `repoman install-skills`",
        )
    )

    manifest = root / skills_dir / MANIFEST
    if manifest.exists():
        current = f"repoman version: {version('repoman')}"
        fresh = current in manifest.read_text()
        out.append(
            SelfCheck(
                "devman:current",
                "ok" if fresh else "warn",
                "up to date" if fresh else "assets stale — re-run `repoman install-skills`",
            )
        )

    return out
