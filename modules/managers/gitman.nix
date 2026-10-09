# RepoMan manager wiring: gitman (version control: native jj + colocated git).
#
# Imported unconditionally by ../devenv.nix; activates only when "git" is in
# the project manifest roster.
#
# gitman 0.12 opens workspaces and runs no other command. It needs no Rust, no maturin,
# and no pyjutsu. The module adds only `git`, for the colocated repository. jj itself
# comes from the host profile (on PATH). A manager module may add system packages and
# language toolchains; this one needs only a package.
{ pkgs, lib, config, repomanManagers, ... }:

let
  cfg = config.repoman;
  enabled = cfg.enable && builtins.elem "git" repomanManagers;
in
{
  config = lib.mkIf enabled {
    packages = [ pkgs.git ];
  };
}
