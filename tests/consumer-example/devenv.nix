# Consumer side of the spike: enable RepoMan with the full roster from
# `.repoman/project.toml`. The manager CLIs come from Vendomat's store closure.
{ ... }:

{
  repoman.enable = true;

  # Python toolchain. This venv hosts the APP + testee (a uv dev dependency
  # declared in pyproject.toml) — not the manager CLIs.
  languages.python = {
    enable = true;
    version = "3.13";            # cp313-abi3 wheel floor (DESIGN §9 / README constraints)
    venv.enable = true;
    uv.enable = true;
  };
}
