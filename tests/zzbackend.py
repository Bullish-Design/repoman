"""A dependency-free PEP 517 backend for the toolchain-coherence fixtures.

`test_toolchain_coherence.py` needs a `path:` manager that a real `uv pip install`
can build with no network and no build dependency. Hatchling or setuptools would
need a download; this backend needs nothing. It reads `[project]` out of the
project's own `pyproject.toml`, so a test changes the fixture's version or
requirements by rewriting that file — exactly how a real checkout advances.
"""

from __future__ import annotations

import tomllib
import zipfile
from pathlib import Path

WHEEL = "Wheel-Version: 1.0\nGenerator: zzbackend\nRoot-Is-Purelib: true\nTag: py3-none-any\n"


def _project() -> dict:
    # PEP 517 runs every hook with the source tree as the working directory.
    with open("pyproject.toml", "rb") as fh:
        return tomllib.load(fh)["project"]


def _metadata(project: dict) -> str:
    lines = [
        "Metadata-Version: 2.1",
        f"Name: {project['name']}",
        f"Version: {project['version']}",
    ]
    lines += [f"Requires-Dist: {req}" for req in project.get("dependencies", [])]
    return "\n".join(lines) + "\n"


def _build(wheel_directory: str, *, editable: bool) -> str:
    project = _project()
    name, version = project["name"], project["version"]
    dist = f"{name}-{version}"
    path = Path(wheel_directory) / f"{dist}-py3-none-any.whl"
    records: list[str] = []
    with zipfile.ZipFile(path, "w") as zf:

        def add(arc: str, text: str) -> None:
            zf.writestr(arc, text)
            records.append(arc)

        if editable:
            add(f"_{name}_editable.pth", str(Path.cwd() / "src") + "\n")
        else:
            add(f"{name}/__init__.py", (Path.cwd() / "src" / name / "__init__.py").read_text())
        add(f"{dist}.dist-info/METADATA", _metadata(project))
        add(f"{dist}.dist-info/WHEEL", WHEEL)
        zf.writestr(
            f"{dist}.dist-info/RECORD",
            "".join(f"{arc},,\n" for arc in records) + f"{dist}.dist-info/RECORD,,\n",
        )
    return path.name


def get_requires_for_build_wheel(config_settings=None) -> list[str]:
    return []


def get_requires_for_build_editable(config_settings=None) -> list[str]:
    return []


def get_requires_for_build_sdist(config_settings=None) -> list[str]:
    return []


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None) -> str:
    return _build(wheel_directory, editable=False)


def build_editable(wheel_directory, config_settings=None, metadata_directory=None) -> str:
    return _build(wheel_directory, editable=True)
