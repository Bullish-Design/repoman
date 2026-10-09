# RepoMan manager wiring: testee (verification).
#
# Imported unconditionally by ../devenv.nix; activates only when "test" is in
# the project manifest roster. Testee v2 runs its wrapper from the host profile,
# then opens one clean devenv shell for the declared checks. The package version
# comes from the Testee Nix module pinned in the consumer's devenv.
#
# Consumers must set `testee.package` and declare their own `testee.checks`.
# RepoMan supplies no default checks. For example:
#
#   testee.checks.pytest = {
#     argv = [ "uv" "run" "pytest" "-q" ];
#     profiles = [ "quick" "full" ];
#   };
{ lib, config, repomanManagers, ... }:

let
  cfg = config.repoman;
  enabled = cfg.enable && builtins.elem "test" repomanManagers;
  testeeBin = ''"''${REPOMAN_TESTEE_HOST_BIN:-$HOME/.nix-profile/bin/testee}"'';
in
{
  config = lib.mkIf enabled {
    env.REPOMAN_TESTEE_VERSION = lib.removePrefix "testee-" config.testee.package.name;

    # Verification entrypoints, namespaced under repoman:* so the conductor and
    # the underlying tool agree on the surface. testee owns its own report, and
    # RepoMan does not aggregate it — run `testee doctor` to check testee.
    tasks = {
      "repoman:test".exec = ''cd "$DEVENV_ROOT" && ${testeeBin} verify'';
      "repoman:test:ci".exec = ''cd "$DEVENV_ROOT" && ${testeeBin} verify --full'';
    };

    enterTest = ''
      cd "$DEVENV_ROOT" && ${testeeBin} verify --full
    '';
  };
}
