from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "modules" / "scripts" / "repoman-sync.sh"


def test_sync_script_has_no_virtual_environment_provider():
    text = SCRIPT.read_text()
    assert "REPOMAN_TOOLCHAIN_VENV" not in text
    assert "REPOMAN_CLI_PROVIDER" not in text
    assert "--machine" in text  # only the retired-argument error remains


def test_sync_script_uses_the_store_closure():
    text = SCRIPT.read_text()
    assert "REPOMAN_TOOLCHAIN_BIN" in text
    assert "toolchain.json" in text
    assert "install-skills" in text


def test_sync_script_does_not_install_packages():
    text = SCRIPT.read_text()
    assert "uv pip install" not in text
    assert "uv sync" not in text
