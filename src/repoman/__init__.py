# src/repoman/__init__.py
"""Repoman package exports."""

from __future__ import annotations

__all__ = ["__version__"]

# Kept in lockstep with pyproject.toml's `project.version`; test_version_is_in_lockstep
# fails the build if the two drift.
__version__ = "0.6.0"
