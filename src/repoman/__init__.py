# src/repoman/__init__.py
"""Repoman package exports."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

__all__ = ["__version__"]

# READ from the installed distribution, never restated. A hand-written literal here had
# to be bumped in lockstep with pyproject.toml, and a test enforced that — but nothing
# ran the test at release time, so 0.7.4 shipped reporting "repoman 0.7.3". The shared
# toolchain then carried a command whose --version disagreed with the closure's own
# provenance manifest, which is the very question that manifest exists to answer.
#
# Deriving it removes the drift instead of detecting it.
try:
    __version__ = version("repoman")
except PackageNotFoundError:  # a source tree that was never installed
    __version__ = "0+unknown"
