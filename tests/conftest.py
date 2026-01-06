"""Shared pytest fixtures for repoman tests."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _cleanup_test_output(request: pytest.FixtureRequest) -> None:
    """Clean up old test output directories."""
    if hasattr(request, "node"):
        test_dir = Path(request.node.fspath).parent / "test_output"
        if test_dir.exists():
            # Keep only last 5 test runs
            subdirs = sorted(test_dir.iterdir(), key=lambda p: p.stat().st_mtime)
            for old_dir in subdirs[:-5]:
                if old_dir.is_dir():
                    shutil.rmtree(old_dir, ignore_errors=True)
