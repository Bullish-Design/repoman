"""devman — the devenv-literacy layer.

devman is a knowledge product, not a doer: agent **skills**, a distilled **docs
export**, and **articles/recipes** whose single job is to make agents operate
``devenv.sh``-managed repos correctly. It has no CLI of its own.

The assets themselves now live in the **genome** (template-py, under
``template/.agents/``): they ship with the template and are converged by
``copyroom update``. RepoMan's only remaining devman role is linting skill
*ownership* — see :func:`repoman.devman.check.skill_ownership_checks`.
"""

from __future__ import annotations

from .check import skill_ownership_checks

__all__ = ["skill_ownership_checks"]
