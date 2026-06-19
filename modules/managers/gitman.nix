# RepoMan manager wiring: gitman (version control: jujutsu via pyjutsu + colocated git).
#
# Imported unconditionally by ../devenv.nix; activates only when "git" is in
# `repoman.managers`. Unlike the pure-Python managers, gitman needs a NATIVE build:
# pyjutsu (jj-lib via PyO3) compiles with maturin + a Rust toolchain, which this module
# contributes to the consumer's devenv so `repoman-sync`'s uv build succeeds. This is the
# proof that the meta-module can provision nix-level system toolchains, not just venv pip
# installs — and it stays gated on "git", so repos without gitman never pull Rust.
{ pkgs, lib, config, ... }:

let
  cfg = config.repoman;
  enabled = cfg.enable && builtins.elem "git" cfg.managers;
  venvBin = "${config.devenv.state}/venv/bin";
in
{
  config = lib.mkIf enabled {
    # System toolchain for building pyjutsu's native extension. devenv merges
    # `packages` across modules, so re-listing git (already present via base/testee)
    # is harmless. languages.rust matches gitman's own devenv (rolling nixpkgs' stable
    # rustc satisfies jj-lib 0.38's Rust >= 1.89 / edition 2024).
    packages = [ pkgs.git pkgs.maturin ];
    languages.rust.enable = true;

    tasks = {
      "repoman:vc:status".exec = ''cd "$DEVENV_ROOT" && ${venvBin}/gitman status'';
    };
  };
}
