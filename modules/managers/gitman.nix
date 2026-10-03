# RepoMan manager wiring: gitman (version control: jujutsu via pyjutsu + colocated git).
#
# Imported unconditionally by ../devenv.nix; activates only when "git" is in
# the project manifest roster.
#
# gitman needs no Rust and no maturin. pyjutsu (jj-lib through PyO3) ships as a
# prebuilt abi3 wheel from a GitHub release. gitman pins that wheel by URL in its
# [tool.uv.sources]. uv carries the pin into a consumer's lock. The wheel serves
# CPython 3.13 and later on x86-64 Linux with glibc 2.39 or newer. So the default
# path pulls zero Rust.
#
# `repoman.nativeBuild` is opt-in: the default is false. When true, it adds maturin and
# languages.rust. Set it only for a consumer that must build pyjutsu from source. One
# case is a platform with no prebuilt wheel. The option stays gated on "git", so a repo
# without gitman never pulls Rust. It also shows the pattern: a manager module may add
# system packages and language toolchains.
{ pkgs, lib, config, repomanManagers, ... }:

let
  cfg = config.repoman;
  enabled = cfg.enable && builtins.elem "git" repomanManagers;
in
{
  options.repoman.nativeBuild = lib.mkOption {
    type = lib.types.bool;
    default = false;
    description = ''
      Provision a Rust toolchain and maturin, so the consumer compiles pyjutsu's native
      extension in-repo. Opt-in: the default is false. pyjutsu ships as a prebuilt abi3
      wheel. Set this to true only for a consumer that must build pyjutsu from source.
    '';
  };

  config = lib.mkIf enabled (lib.mkMerge [
    {
      # git is needed whenever the manager is active (colocated git alongside jj).
      packages = [ pkgs.git ];

      tasks = {
        # gitman lives in Vendomat's shared store closure, resolved at runtime.
        # Not a bare `gitman`: the task exec must not depend on PATH state, so it uses the
        # toolchain bin shell expression directly (D1 — devenv tasks may not inherit the
        # shell's PATH prepend).
        "repoman:vc:status".exec = ''cd "$DEVENV_ROOT" && "${cfg.toolchainBin}"/gitman status'';
      };
    }

    # System toolchain for building pyjutsu's native extension from source. Opt-in only.
    # A consumer that installs the prebuilt wheel leaves this off and pulls zero Rust.
    # This matches pyjutsu's own devenv (maturin + languages.rust), not gitman's:
    # gitman's devenv has no Rust. pyjutsu's Cargo.toml needs Rust 1.89 or newer
    # (edition 2024) and pins jj-lib 0.44.0. The stable rustc in rolling nixpkgs meets that.
    (lib.mkIf cfg.nativeBuild {
      packages = [ pkgs.maturin ];
      languages.rust.enable = true;
    })
  ]);
}
