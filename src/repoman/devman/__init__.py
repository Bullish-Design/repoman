"""Agent-surface ownership checks retained under RepoMan's ``devman`` namespace.

The actual ``devman`` automation plane is a separate input and devenv module.
RepoMan does not ship its CLI or install its static assets. Shared devenv
literacy content lives in the **genome** (template-py, under
``template/.agents/``) and is converged by ``copyroom update``.

This namespace contains only RepoMan's ownership lint for the shared agent
surface — see :func:`repoman.devman.check.skill_ownership_checks`.
"""

from __future__ import annotations

from .check import skill_ownership_checks

__all__ = ["skill_ownership_checks"]
