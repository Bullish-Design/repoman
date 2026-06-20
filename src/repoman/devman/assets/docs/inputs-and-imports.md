# inputs & imports — devenv.yaml

## Shape

    # devenv.yaml
    inputs:
      nixpkgs:
        url: github:cachix/devenv-nixpkgs/rolling
      repoman:
        url: path:../repoman/modules     # or github:Owner/repo?dir=modules
        flake: false
    imports:
      - repoman

## Three rules

1. **`flake: false` on a devenv-module input.** A module imported for its `devenv.nix` is *not* a
   flake; without `flake: false`, devenv tries to evaluate it as one and the import fails.

2. **`nixpkgs-python` for `languages.python.version` pins.** Add the input or the version pin is
   silently ignored. See `languages-python.md`.

3. **Imports merge `devenv.nix`, not `devenv.yaml`.** Importing a remote module pulls in its
   `devenv.nix`, but **not** its inputs. Any input that module depends on must be declared again in
   *your* `devenv.yaml` (transitive inputs are your responsibility).

## After editing devenv.yaml

Re-lock so the change takes:

    rm -f devenv.lock          # re-locks all inputs on next entry
    devenv update <input>      # re-lock one input

See `lock-and-cache.md`. (Trigger: the `devenv-inputs` skill.)
