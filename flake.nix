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
          default = pkgs.python312Packages.buildPythonApplication {
            pname = "repoman";
            # Source the version from pyproject.toml so the flake package can't
            # drift behind the project (it previously hard-coded 0.1.0).
            version = (builtins.fromTOML (builtins.readFile ./pyproject.toml)).project.version;
            src = self;
            pyproject = true;
            build-system = with pkgs.python312Packages; [
              setuptools
              wheel
            ];
            # Only the real runtime deps from pyproject.toml. pyyaml/tomli/aiofiles
            # were cargo-culted from a template; tomllib is stdlib (python 3.11+).
            propagatedBuildInputs = with pkgs.python312Packages; [
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
        in
        {
          gitman-rust-gate =
            assert rustEnabled false == false;
            assert rustEnabled true == true;
            pkgs.runCommand "gitman-rust-gate-ok" { } "touch $out";
        });

      devShells = forAllSystems (system:
        let
          pkgs = import nixpkgs { inherit system; };
        in
        {
          default = pkgs.mkShell {
            packages = [
              pkgs.python312
              pkgs.uv
              pkgs.git
            ];
          };
        });
    };
}
