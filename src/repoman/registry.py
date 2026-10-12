"""The RepoMan manager roster.

Maps each manager key (used in the project manifest) to the console script that
implements it and its tier. The host profile puts every command on ``PATH``, and
RepoMan runs each one by name. RepoMan never models a manager's report.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Manager:
    """One entry in the roster.

    Attributes:
        key: Short manager key (e.g. ``"test"``). The nix module reads these keys from
            `.repoman/project.toml`. The Python CLI never reads that file: it gets
            the roster from ``REPOMAN_MANAGERS``, which the nix module exports.
        command: Console script name on ``PATH`` (e.g. ``"testee"``).
        tier: ``"core"`` | ``"publish"`` | ``"situational"``.
        summary: One-line description for ``repoman managers``.
        skill: Name of the manager's own skill; defaults to ``command``.
        route_when: The "when you want to…" cell in the router's routing table.
        min_version: Oldest version that ``<command> --version`` may report; ``""`` skips
            the ``version:<key>`` doctor row.
    """

    key: str
    command: str
    tier: str
    summary: str
    skill: str = ""
    route_when: str = ""
    min_version: str = ""

    def __post_init__(self) -> None:
        if not self.skill:
            object.__setattr__(self, "skill", self.command)


# The lifecycle spine: three ordered phases, as (label, manager-key | None). The
# entrypoint skill renders a phase only when its manager is enabled. "change" (key
# None) is the human/agent edit phase and always appears.
#
# Two laws are the whole policy: verify before you integrate, and never integrate on red.
SPINE: tuple[tuple[str, str | None], ...] = (
    ("change", None),
    ("verify", "test"),
    ("integrate", "git"),
)

# Activities have no order. They run on their own cadence, outside the spine.
# Each renders only when its manager is enabled.
ACTIVITIES: tuple[tuple[str, str | None], ...] = (("birth / converge", "copy"),)


REGISTRY: dict[str, Manager] = {
    "copy": Manager(
        "copy",
        "copyroom",
        "core",
        "Templating / scaffolding / convergence (Copier)",
        route_when="scaffold a repo, pull template updates, or check template drift",
    ),
    "git": Manager(
        "git",
        "gitman",
        "core",
        "Version control (native jj and gh; gitman opens workspaces)",
        route_when="open a workspace with `gitman work`; remove a finished one with `gitman done`; use native jj and `gh` to describe, bookmark, push, and open a PR",
    ),
    "test": Manager(
        "test",
        "testee",
        "core",
        "Verification (a verdict per commit)",
        route_when="verify a commit and read its verdict",
        min_version="0.6.0",  # `testee verify` is a full gate; `testee status -r` reads the verdict
    ),
}

DEFAULT_MANAGERS: list[str] = ["copy", "git", "test"]

#: Manager keys that RepoMan once shipped and no longer does, with the release that
#: removed each one. A roster that still names one gets a doctor warning, not a crash.
REMOVED_MANAGERS: dict[str, str] = {"doc": "0.13.0"}
