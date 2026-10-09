# Consumer side of the spike: enable RepoMan with the full roster from
# `.repoman/project.toml`. The host profile puts the managers on PATH.
{ pkgs, ... }:

let
  testeeFlake = builtins.getFlake "git+https://github.com/Bullish-Design/testee?ref=refs/tags/v0.5.0";
in

{
  imports = [ testeeFlake.devenvModules.default ];

  testee.package = testeeFlake.packages.${pkgs.stdenv.hostPlatform.system}.testee;
  repoman.enable = true;

  # The venv hosts the app and check tools. Testee's wrapper comes from the host.
  languages.python = {
    enable = true;
    version = "3.13";            # cp313-abi3 wheel floor (DESIGN §9 / README constraints)
    venv.enable = true;
    uv.enable = true;
  };
}
