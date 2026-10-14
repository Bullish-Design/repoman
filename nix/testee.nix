# Testee checks for this project.
#
# The machine (nix-meta) supplies the Testee module at the `machine` path.
# On a host without that module, the checks are skipped and the shell still
# evaluates. This project owns its checks here. It never pins Testee itself.
# Use `lib.optionalAttrs` for the settings. A module-system condition fails
# when the option is absent.
{ lib, options, pkgs, ... }:

let
  machine = /run/current-system/sw/share/testee/module/testee.nix;
in
{
  imports = lib.optional (builtins.pathExists machine) machine;

  config = lib.optionalAttrs (options ? testee) {
    # The host `testee` runs these checks in its own workspace, so `uv sync` there
    # makes the venv follow uv.lock.
    testee.prepare = [ [ "uv" "sync" "--locked" "--all-extras" ] ];
    testee.checks = {
      ruff = {
        argv = [ "${pkgs.bash}/bin/bash" "-c" "uv run --no-sync ruff check . --output-format json" ];
        profiles = [ "quick" "full" ];
        structured = { parser = "ruff-json"; file = "ruff.stdout.log"; };
      };
      ruff-format = {
        argv = [ "${pkgs.bash}/bin/bash" "-c" "uv run --no-sync ruff format --check ." ];
        profiles = [ "quick" "full" ];
      };
      ty = {
        argv = [ "${pkgs.bash}/bin/bash" "-c" "uv run --no-sync ty check ." ];
        profiles = [ "full" ];
      };
      pytest = {
        argv = [ "${pkgs.bash}/bin/bash" "-c" ''uv run --no-sync pytest -q --junitxml="$TESTEE_RUN_DIR/pytest.junit.xml"'' ];
        profiles = [ "full" ];
        structured = { parser = "junit-xml"; file = "pytest.junit.xml"; };
      };
    };
  };
}
