# RepoMan manager wiring: gitman (version control: jujutsu via pyjutsu + colocated git).
#
# Imported unconditionally by ../devenv.nix; activates only when "git" is in
# `repoman.managers`. gitman's native dep pyjutsu (jj-lib via PyO3) is normally vended as
# a prebuilt wheel by vendomat (repoman.lock `source = "wheel:…"`), so the default path
# pulls ZERO Rust. The native toolchain (maturin + languages.rust) is an explicit opt-out:
# set `repoman.nativeBuild = true` in pyjutsu's own repo, or any consumer with no vendomat
# wheelhouse, to compile pyjutsu from source. When on, this is the proof that the
# meta-module can provision nix-level system toolchains, not just venv pip installs; and it
# stays gated on "git", so repos without gitman never pull Rust regardless.
{ pkgs, lib, config, ... }:

let
  cfg = config.repoman;
  enabled = cfg.enable && builtins.elem "git" cfg.managers;
in
{
  options.repoman.nativeBuild = lib.mkOption {
    type = lib.types.bool;
    default = false;
    description = ''
      Provision a Rust toolchain + maturin so pyjutsu's native extension is compiled
      in-repo. Leave false (default) when pyjutsu installs as a prebuilt wheel via
      vendomat (repoman.lock `source = "wheel:…"`). Set true only in pyjutsu's OWN repo
      or a consumer with no vendomat wheelhouse, which must compile pyjutsu itself.
    '';
  };

  config = lib.mkIf enabled (lib.mkMerge [
    {
      # git is needed whenever the manager is active (colocated git alongside jj).
      packages = [ pkgs.git ];

      tasks = {
        # gitman lives in the SYSTEM-WIDE toolchain venv (project 12), resolved at runtime.
        # Not a bare `gitman`: the task exec must not depend on PATH state, so it uses the
        # toolchain bin shell expression directly (D1 — devenv tasks may not inherit the
        # shell's PATH prepend).
        "repoman:vc:status".exec = ''cd "$DEVENV_ROOT" && "${cfg.toolchainBin}"/gitman status'';
      };
    }

    # System toolchain for building pyjutsu's native extension — only when explicitly
    # opted in. Consumers using a vendomat `wheel:` source leave this off and pull zero
    # Rust. languages.rust matches gitman's own devenv (rolling nixpkgs' stable rustc
    # satisfies jj-lib 0.38's Rust >= 1.89 / edition 2024).
    (lib.mkIf cfg.nativeBuild {
      packages = [ pkgs.maturin ];
      languages.rust.enable = true;
    })
  ]);
}
