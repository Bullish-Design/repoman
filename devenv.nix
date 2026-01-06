{ pkgs, ... }:
{
  packages = [
    # pkgs.python312
    # pkgs.uv
    pkgs.git
  ];

  languages = {
    python = {
      enable = true;
      version = "3.12";
      venv.enable = true;
      uv.enable = true;

      # Python packages
      # Note: The main dependencies are installed via pyproject.toml
      # These are additional system-level tools
    };
  };
}
