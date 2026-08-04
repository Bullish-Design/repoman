import repoman.aggregate as agg
from repoman.aggregate import SubResult, worst_exit
from repoman.registry import REGISTRY


def _r(code, available=True):
    return SubResult("m", ["m"], code, available)


def test_worst_exit_severity_order():
    assert worst_exit([_r(0), _r(1), _r(0)]) == 1
    assert worst_exit([_r(1), _r(2)]) == 2
    assert worst_exit([_r(0), _r(3)]) == 3
    assert worst_exit([]) == 0


def test_unavailable_counts_as_infra():
    assert worst_exit([_r(0, available=False)]) == 2


def test_unknown_code_maps_to_infra():
    assert worst_exit([_r(127)]) == 2


def test_run_sub_missing_command_is_unavailable(monkeypatch):
    monkeypatch.setattr(agg.shutil, "which", lambda _c: None)
    res = agg.run_sub(REGISTRY["test"], ["doctor"])
    assert res.available is False and res.exit_code == 127
    # The reason is what the CLI prints; without it an unavailable manager showed the
    # user a bare header and nothing else.
    assert "not installed" in res.reason and "uv sync" in res.reason


def test_run_sub_missing_toolchain_command_points_at_the_machine_sync(monkeypatch):
    monkeypatch.setattr(agg.shutil, "which", lambda _c: None)
    res = agg.run_sub(REGISTRY["git"], ["doctor"])
    assert "repoman-sync --machine" in res.reason


def test_run_sub_prefers_the_binary_the_tasks_exec(tmp_path, monkeypatch):
    # `repoman doctor` and `devenv tasks run` must never disagree about which copy of a
    # manager is in play, so the absolute toolchain path wins over a PATH hit.
    toolchain = tmp_path / "toolchain"
    (toolchain / "bin").mkdir(parents=True)
    (toolchain / "bin" / "gitman").write_text("")
    monkeypatch.setenv("REPOMAN_TOOLCHAIN_VENV", str(toolchain))
    monkeypatch.setattr(agg.shutil, "which", lambda _c: "/somewhere/else/gitman")
    assert agg.resolve(REGISTRY["git"]) == str(toolchain / "bin" / "gitman")

    seen = []

    class P:
        returncode = 0

    monkeypatch.setattr(agg.subprocess, "run", lambda cmd, **kwargs: (seen.append(cmd), P())[1])
    agg.run_sub(REGISTRY["git"], ["doctor"])
    assert seen == [[str(toolchain / "bin" / "gitman"), "doctor"]]


def test_run_sub_falls_back_to_path_when_no_absolute_path_is_known(monkeypatch):
    monkeypatch.setattr(agg.shutil, "which", lambda c: "/usr/bin/" + c)
    assert agg.resolve(REGISTRY["test"]) == "/usr/bin/testee"


def test_run_sub_timeout_is_infra_not_a_hang(monkeypatch):
    monkeypatch.setattr(agg.shutil, "which", lambda c: "/usr/bin/" + c)

    def boom(cmd, **kwargs):
        raise agg.subprocess.TimeoutExpired(cmd, 900)

    monkeypatch.setattr(agg.subprocess, "run", boom)
    res = agg.run_sub(REGISTRY["test"], ["doctor"])
    assert res.available is False and res.exit_code == 2
    assert "timed out" in res.reason
    assert worst_exit([res]) == 2


def test_run_sub_reports_exec_failure_instead_of_raising(monkeypatch):
    monkeypatch.setattr(agg.shutil, "which", lambda c: "/usr/bin/" + c)

    def boom(cmd, **kwargs):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(agg.subprocess, "run", boom)
    res = agg.run_sub(REGISTRY["test"], ["doctor"])
    assert res.available is False and res.exit_code == 2
    assert "Permission denied" in res.reason


def test_sub_timeout_is_configurable(monkeypatch):
    monkeypatch.setenv("REPOMAN_SUB_TIMEOUT", "5")
    assert agg._timeout() == 5.0
    monkeypatch.setenv("REPOMAN_SUB_TIMEOUT", "0")  # 0 = deliberately no ceiling
    assert agg._timeout() is None
    monkeypatch.setenv("REPOMAN_SUB_TIMEOUT", "not-a-number")
    assert agg._timeout() == agg._DEFAULT_TIMEOUT


def test_run_sub_invokes_present_command(monkeypatch):
    monkeypatch.setattr(agg.shutil, "which", lambda _c: "/usr/bin/" + _c)

    class P:
        returncode = 1

    monkeypatch.setattr(agg.subprocess, "run", lambda cmd, **kwargs: P())
    res = agg.run_sub(REGISTRY["test"], ["doctor"])
    assert res.available is True and res.exit_code == 1
