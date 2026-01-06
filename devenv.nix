{ pkgs, ... }:
{
  packages = [
    pkgs.python312
    pkgs.uv
    pkgs.git
  ];

  languages.python.enable = true;
  languages.python.package = pkgs.python312;
}
