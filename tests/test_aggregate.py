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


def test_run_sub_invokes_present_command(monkeypatch):
    monkeypatch.setattr(agg.shutil, "which", lambda _c: "/usr/bin/" + _c)

    class P:
        returncode = 1

    monkeypatch.setattr(agg.subprocess, "run", lambda cmd: P())
    res = agg.run_sub(REGISTRY["test"], ["doctor"])
    assert res.available is True and res.exit_code == 1
