# RepoMan manager wiring: mypi-agent (coding-agent runtime + per-repo secrets — Pi).
#
# Imported unconditionally by ../devenv.nix; activates only when "agent" is in
# `repoman.managers`. agent is an APPROACH-B manager: the `mypi` CLI's doctor reads a
# wall of env (NPM_CONFIG_*, MYPI_*, PI_CODING_AGENT_DIR) and needs node + project-local
# npm scoping that live in mypi-agent's OWN reusable module (`<mypi-agent>/modules/pi-agent.nix`).
# We presence-import that module and activate it gated on roster membership.
#
# SAFE-BRIDGE policy (deliberate): we bridge the env/node/scripts so `mypi doctor` /
# `mypi sync` work when the user opts in, but we DO NOT let the module's defaults run on
# shell entry — no on-entry `mypi sync` (network npm), no secret scaffolding writes, no
# Telegram install, no usage banner. The actual `mypi sync` + real secret values stay
# user-driven. Two mypi-specific wrinkles handled below:
#   - pi-agent.nix's `piAgent.enable` defaults TRUE, so we set it to `enabled` explicitly
#     (false when "agent" isn't selected) — otherwise merely declaring the input would
#     activate it uninvited.
#   - its `scripts.mypi`/`secretspec-setup` point at a nix-built mypi (version skew vs the
#     repoman-pinned venv CLI), so we override them to the venv `mypi` — which also avoids
#     building the nix CLI package at all.
{ inputs ? {}, pkgs, lib, config, ... }:

let
  cfg = config.repoman;
  enabled = cfg.enable && builtins.elem "agent" cfg.managers;
  venvBin = "${config.devenv.state}/venv/bin";
  hasInput = inputs ? mypi-agent;

  # Make a mypi-family script call the venv (repoman-pinned) CLI instead of pi-agent.nix's
  # nix-built one.
  venvMypi = subcmd: lib.mkForce ''
    set -euo pipefail
    if [ -n "''${DEVENV_ROOT:-}" ]; then cd "$DEVENV_ROOT"; fi
    exec ${venvBin}/mypi ${subcmd}"$@"
  '';
in
{
  imports = lib.optional hasInput (inputs.mypi-agent + "/modules/pi-agent.nix");

  config = lib.mkMerge [
    # Gate the imported module on membership. `enable` defaults TRUE upstream, so set it to
    # `enabled` explicitly. The safe-bridge knobs are mkDefault so a consumer can opt back in.
    (lib.optionalAttrs hasInput {
      piAgent.enable = enabled;
      piAgent.bootstrap.mode = lib.mkDefault "manual_only";   # never npm-install on shell entry
      piAgent.telegram.enable = lib.mkDefault false;          # no telegram npm install
      piAgent.showUsageOnEntry = lib.mkDefault false;         # no entry banner
      piAgent.secrets.enable = lib.mkDefault false;           # no secret scaffolding writes on entry
    })
    # Resolve the CLI-shadow only when the manager is actually active (so a consumer that
    # declared the input but didn't select "agent" gets no stray `mypi` script).
    (lib.optionalAttrs hasInput (lib.mkIf enabled {
      scripts.mypi.exec = venvMypi "";
      scripts.secretspec-setup.exec = venvMypi "secretspec-setup ";
      # Signal nix-layer provisioning presence to `repoman doctor` (checks.py).
      env.REPOMAN_PROVISIONED_AGENT = "1";
    }))
    # Always-on when "agent" is selected: the secretspec binary mypi's secrets verbs drive,
    # plus the aggregation tasks. `repoman doctor` calls the venv mypi (absolute path) so it
    # works whether or not the module's provisioning is present.
    (lib.mkIf enabled {
      packages = [ pkgs.secretspec ];
      tasks = {
        "repoman:agent:status".exec = ''cd "$DEVENV_ROOT" && ${venvBin}/mypi paths'';
        "repoman:agent:doctor".exec = ''cd "$DEVENV_ROOT" && ${venvBin}/mypi doctor'';
      };
    })
  ];
}
