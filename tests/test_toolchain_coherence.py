from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "modules" / "scripts" / "repoman-sync.sh"


def test_sync_script_reads_no_toolchain_closure():
    text = SCRIPT.read_text()
    for retired in ("REPOMAN_TOOLCHAIN_VENV", "REPOMAN_CLI_PROVIDER", "REPOMAN_TOOLCHAIN_BIN", "toolchain.json"):
        assert retired not in text
    assert "--machine" not in text


def test_sync_script_installs_the_router_only():
    text = SCRIPT.read_text()
    assert "install-skills" in text
    assert "uv pip install" not in text
    assert "uv sync" not in text
