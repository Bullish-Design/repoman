"""The RepoMan manager roster.

Maps each manager key (used in ``repoman.managers``) to the console script that
implements it, its tier, and the sub-commands RepoMan calls when aggregating
``doctor`` / ``status``. RepoMan never models a manager's report — it only knows
*how to invoke* each one.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Manager:
    """One entry in the roster.

    Attributes:
        key: Short key used in ``repoman.managers`` (e.g. ``"test"``).
        command: Console script name on PATH (e.g. ``"testee"``).
        tier: ``"core"`` | ``"publish"`` | ``"situational"``.
        doctor: Args for this manager's doctor (every manager has one).
        status: Args for a status-like read, or ``None`` if it has none.
        summary: One-line description for ``repoman managers``.
        nix_input: For an approach-B manager, the ``devenv.yaml`` input its nix
            module needs (presence-gated import); ``""`` for approach-A /
            pure-Python managers that need no consumer-declared input.
        install: ``"toolchain"`` (default) — the manager lives in the system-wide
            shared toolchain venv, installed from the machine ``repoman.lock`` by
            ``repoman-sync --machine``; ``"uv"`` — the manager is declared as a
            dependency in the consumer's ``pyproject.toml`` and installed by
            ``uv sync`` (its ``doctor`` check is ``uv:<key>``, not ``lock:<key>``).
        package: Distribution name on the index; defaults to ``command``. Used to
            find the manager in ``pyproject.toml`` for uv-declared managers.
    """

    key: str
    command: str
    tier: str
    summary: str
    doctor: list[str] | None = field(default_factory=lambda: ["doctor"])
    status: list[str] | None = None
    skill: str = ""  # sub-skill name the entrypoint routes to (default: command)
    route_when: str = ""  # "when you want to…" cell in the routing table
    nix_input: str = ""  # devenv.yaml input the manager's approach-B nix module needs; "" = none
    install: str = "toolchain"  # "toolchain" = system-wide shared venv (machine repoman.lock);
                                # "uv" = declared in the consumer's pyproject.toml, installed by uv sync
    package: str = ""           # distribution name; defaults to `command`

    def __post_init__(self) -> None:
        if not self.skill:
            object.__setattr__(self, "skill", self.command)
        if not self.package:
            object.__setattr__(self, "package", self.command)
        if self.install not in {"toolchain", "uv"}:
            raise ValueError(f"{self.key}: unknown install model {self.install!r}")


# Canonical lifecycle spine: ordered (label, manager-key | None). The entrypoint
# skill renders only the steps whose manager is enabled; "change" (key None) is the
# human/agent edit step and always appears.
SPINE: list[tuple[str, str | None]] = [
    ("scaffold", "copy"),
    ("change", None),
    ("verify", "test"),
    ("save", "git"),
    ("docs", "doc"),
]


REGISTRY: dict[str, Manager] = {
    "copy": Manager(
        "copy",
        "copyroom",
        "core",
        "Templating / scaffolding / convergence (Copier)",
        doctor=["doctor"],  # copyroom 0.6+ ships `doctor` (env + agent-files checks)
        status=["status"],
        route_when="scaffold a repo, pull template updates, or check template drift",
    ),
    "git": Manager(
        "git",
        "gitman",
        "core",
        "Version control (jujutsu + colocated git)",
        status=["status"],
        route_when="commit, branch, land, undo, or release",
    ),
    "test": Manager(
        "test",
        "testee",
        "core",
        "Verification (pytest / ruff / ty)",
        status=["list-runs"],
        route_when="verify code health, fix lint/format, or rerun failures",
        # testee's TOOLS (pytest/ruff/ty) import the consumer's code, so testee is a per-repo
        # uv dev dependency, not a shared-toolchain package. See CONCEPT.md §3 (project 12).
        install="uv",
    ),
    "doc": Manager(
        "doc",
        "docman",
        "publish",
        "Docs build/lint/check (zensical)",
        route_when="build or check the docs",
        nix_input="docman",
    ),
}

DEFAULT_MANAGERS: list[str] = ["copy", "git", "test"]
