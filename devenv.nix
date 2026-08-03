{ pkgs, config, ... }:
{
  env = {
    DEVENV_PROJECT = "repoman";
  };

  packages = with pkgs; [
    git
    curl
    jq
  ];

  # Machine bootstrap (project 12): export UV_FIND_LINKS at vendomat's prebuilt pyjutsu
  # wheelhouse so `repoman-sync --machine` can resolve the `wheel:pyjutsu` source in the
  # machine repoman.lock. Consumers no longer need the vendomat input (the toolchain is
  # system-wide); repoman's own devenv is the one place that must still resolve wheels.
  vendor.enable = true;
  vendor.libs = [ "pyjutsu" ];

  scripts = {
    repoman-sync = {
      description = "Sync the SYSTEM-WIDE repoman toolchain venv from this checkout's repoman.lock.";
      exec = ''REPOMAN_ROOT="''${DEVENV_ROOT:-$PWD}" exec ${pkgs.bash}/bin/bash ${./modules/scripts/repoman-sync.sh} "$@"'';
    };

    test = {
      exec = ''
        pytest "$@"
      '';
      description = "Run tests with pytest";
    };

    format = {
      exec = ''
        ruff format src/ tests/
      '';
      description = "Format code with ruff";
    };

    lint = {
      exec = ''
        ruff check src/ tests/
      '';
      description = "Lint code with ruff";
    };
  };

  languages = {
    python = {
      enable = true;
      version = "3.12";
      venv.enable = true;
      uv.enable = true;
    };
  };

  enterShell = ''
    echo ""
    echo "╔════════════════════════════════════════════╗"
    echo "║             repoman devenv                 ║"
    echo "╚════════════════════════════════════════════╝"
    echo ""
    echo "🐍 Python: $(python --version)"
    echo ""
    echo "Available commands:"
    echo "  test   - Run tests with pytest"
    echo "  format - Format code with ruff"
    echo "  lint   - Lint code with ruff"
    echo ""
    echo "Quick start:"
    echo "  0. Bootstrap the shared toolchain: repoman-sync --machine"
    echo "  1. Install dependencies: uv sync --all-extras"
    echo "  2. Run tests: test"
    echo ""
  '';
}
