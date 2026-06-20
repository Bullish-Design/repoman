"""devman — the devenv-literacy layer, shipped as a subsystem of repoman.

devman is a knowledge product, not a doer: agent **skills**, a distilled **docs
export**, and **articles/recipes** whose single job is to make Claude Code agents
operate ``devenv.sh``-managed repos correctly. It has no CLI of its own — it is
installed by ``repoman install-skills`` (run from ``repoman-sync``) and lint-checked
by ``repoman doctor`` via :func:`repoman.devman.check.devman_checks`.
"""

from __future__ import annotations
