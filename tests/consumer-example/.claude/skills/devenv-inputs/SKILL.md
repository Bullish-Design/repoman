---
name: devenv-inputs
description: Use when editing devenv.yaml or adding an input/import. Covers flake:false for modules, nixpkgs-python for version pins, and transitive inputs.
auto_trigger:
  keywords: ["devenv.yaml", "add input", "add import", "flake false", "nixpkgs-python", "module input", "transitive input", "version pin nix"]
---

# Adding inputs & imports in devenv.yaml

Three rules cover most input mistakes:

1. **A devenv-module input needs `flake: false`.** Without it, devenv tries to evaluate the input
   as a flake and the import fails.

       inputs:
         repoman:
           url: path:../repoman/modules
           flake: false

2. **Pinning `languages.python.version` needs the `nixpkgs-python` input.** A bare version string
   with no such input silently won't resolve.

3. **Remote module imports merge `devenv.nix`, not `devenv.yaml`.** A module you import does **not**
   bring its own inputs along — you must declare its transitive inputs in *your* `devenv.yaml`.

After any `devenv.yaml` change, re-lock: `rm -f devenv.lock` (or `devenv update <input>`) — see the
`devenv-module-edits` skill. Grep-able detail: `inputs-and-imports.md`.

For *when* in the lifecycle to do this, see the `repoman` skill.
