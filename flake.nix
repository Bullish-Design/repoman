{
  # Keep the description in sync with pyproject.toml; this is the first line a
  # Nix-oriented reader sees and it must not describe the old wiped concept.
  description = "The agentic repo lifecycle conductor for devenv.sh repos — one import that composes the *man manager family.";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
    in
    {
      packages = forAllSystems (system:
        let
          pkgs = import nixpkgs { inherit system; };
        in
        {
          # Project 039: install the meta-module tree into `$out/share/repoman/module/`
          # so a machine can pin repoman ONCE (in nix-meta) instead of every consumer
          # pinning it in its own devenv.yaml. Copies the whole `modules/` tree, not one
          # file — `modules/devenv.nix` imports `managers/*.nix` and
          # `scripts/repoman-sync.sh` by relative path (devman/nix/link-adapter.nix is
          # the pattern this follows).
          repoman-module = pkgs.runCommand "repoman-module" { } ''
            mkdir -p "$out/share/repoman"
            cp -r ${self}/modules "$out/share/repoman/module"
          '';

          default = pkgs.python313Packages.buildPythonApplication {
            pname = "repoman";
            # Source the version from pyproject.toml so the flake package can't
            # drift behind the project (it previously hard-coded 0.1.0).
            version = (builtins.fromTOML (builtins.readFile ./pyproject.toml)).project.version;
            src = self;
            pyproject = true;
            build-system = with pkgs.python313Packages; [
              setuptools
              wheel
            ];
            # Only the real runtime deps from pyproject.toml. pyyaml/tomli/aiofiles
            # were cargo-culted from a template; tomllib is stdlib (python 3.11+).
            propagatedBuildInputs = with pkgs.python313Packages; [
              pydantic
              typer
              jinja2
            ];
          };
        });

      apps = forAllSystems (system: {
        default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/repoman";
        };
      });

      # Project 039: the machine module. `repoman.installConsumerModule` (default
      # true) installs the `repoman-module` package, so `nix-meta` pins repoman ONCE
      # and every consumer imports the module from the stable machine path below
      # instead of pinning `repoman` in its own `devenv.yaml`.
      #
      # `environment.pathsToLink` is NOT optional: NixOS links selected `share`
      # subtrees into the system profile, not all of `/share`. Devman's first switch
      # shipped the binary without the module path and consumers could not import it
      # (038 Stage 18 follow-up) — the same trap applies here.
      nixosModules.default = { config, lib, pkgs, ... }:
        let
          system = pkgs.system;
          cfg = config.repoman or { };
          installConsumerModule =
            if cfg ? installConsumerModule then cfg.installConsumerModule else true;
        in
        {
          options.repoman.installConsumerModule = lib.mkOption {
            type = lib.types.bool;
            default = true;
            description = ''
              Install the repoman devenv module tree at
              /run/current-system/sw/share/repoman/module, so a consumer's
              devenv.local.nix can import it without pinning repoman itself.
            '';
          };

          config = lib.mkIf installConsumerModule {
            environment.systemPackages = [ self.packages.${system}.repoman-module ];
            environment.pathsToLink = [ "/share/repoman" ];
          };
        };

      # Hermetic eval test: gitman.nix must contribute languages.rust ONLY when
      # repoman.nativeBuild = true. Evaluate the module under stub options twice and
      # assert the gate. `nix build .#checks.<system>.gitman-rust-gate` (or `nix flake
      # check`) fails if the opt-out ever regresses to provisioning Rust by default.
      checks = forAllSystems (system:
        let
          pkgs = import nixpkgs { inherit system; };
          lib = pkgs.lib;
          rustEnabled = nativeBuild: (lib.evalModules {
            specialArgs = { inherit pkgs; };
            modules = [
              ({ lib, ... }: {
                options.languages.rust.enable = lib.mkOption { type = lib.types.bool; default = false; };
                options.devenv.state = lib.mkOption { type = lib.types.str; default = "/state"; };
                options.packages = lib.mkOption { type = lib.types.listOf lib.types.unspecified; default = [ ]; };
                options.tasks = lib.mkOption { type = lib.types.attrsOf lib.types.unspecified; default = { }; };
                options.repoman.enable = lib.mkEnableOption "repoman";
                options.repoman.managers = lib.mkOption { type = lib.types.listOf lib.types.str; default = [ ]; };
              })
              ./modules/managers/gitman.nix
              { repoman = { enable = true; managers = [ "git" ]; inherit nativeBuild; }; }
            ];
          }).config.languages.rust.enable;

          # Project 039 Phase 1/2: the module resolves for a fixture consumer with no
          # `.repoman/project.toml` and picks the default roster. Modelled on
          # devman's link-adapter install check: assert the packaged module file
          # exists, that `builtins.functionArgs (import …)` evaluates, and that
          # `evalModules` against a fixture with no manifest resolves the default
          # roster `[ "copy" "git" "test" ]`.
          defaultRosterConsumer = (lib.evalModules {
            specialArgs = { inherit pkgs; inputs = { }; };
            modules = [
              ({ lib, ... }: {
                options.devenv.root = lib.mkOption { type = lib.types.str; default = toString (self + "/.flake-check-fixture-no-manifest"); };
                options.devenv.state = lib.mkOption { type = lib.types.str; default = "/state"; };
                options.packages = lib.mkOption { type = lib.types.listOf lib.types.unspecified; default = [ ]; };
                options.tasks = lib.mkOption { type = lib.types.attrsOf lib.types.unspecified; default = { }; };
                options.env = lib.mkOption { type = lib.types.attrsOf lib.types.unspecified; default = { }; };
                options.scripts = lib.mkOption { type = lib.types.attrsOf lib.types.unspecified; default = { }; };
                options.enterShell = lib.mkOption { type = lib.types.lines; default = ""; };
                options.enterTest = lib.mkOption { type = lib.types.lines; default = ""; };
                options.languages.rust.enable = lib.mkOption { type = lib.types.bool; default = false; };
              })
              (self + "/modules/devenv.nix")
              { repoman.enable = true; }
            ];
          }).config.repoman.managers;
        in
        {
          gitman-rust-gate =
            assert rustEnabled false == false;
            assert rustEnabled true == true;
            pkgs.runCommand "gitman-rust-gate-ok" { } "touch $out";

          repoman-consumer-module =
            let
              moduleFile = self.packages.${system}.repoman-module + "/share/repoman/module/devenv.nix";
              functionArgs = builtins.functionArgs (import moduleFile);
            in
            assert builtins.pathExists moduleFile;
            assert functionArgs ? config;
            assert defaultRosterConsumer == [ "copy" "git" "test" ];
            pkgs.runCommand "repoman-consumer-module-check" { } "touch $out";
        });

      devShells = forAllSystems (system:
        let
          pkgs = import nixpkgs { inherit system; };
        in
        {
          default = pkgs.mkShell {
            packages = [
              pkgs.python313
              pkgs.uv
              pkgs.git
            ];
          };
        });
    };
}
