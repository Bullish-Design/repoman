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

  # Self-hosting (project 14 seam): this shell is a real managed repo with the full roster
  # wired — copy/git/test/doc — so the shared toolchain (copyroom, gitman, docman) is on
  # PATH here and `copyroom new <target> --answers … --trust` can birth new repos from this
  # checkout's shell (no host-repo trick). The meta-module (devenv.yaml `imports: [repoman]`)
  # owns the `repoman-sync` script now — consumer mode installs skills, `--machine` syncs
  # the shared toolchain; repoman-sync.sh itself defaults REPOMAN_ROOT to DEVENV_ROOT.
  repoman = {
    enable = true;
    managers = [ "copy" "git" "test" "doc" ];
  };

  scripts = {
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
      version = "3.13";
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
