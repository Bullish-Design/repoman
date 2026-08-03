# Consumer side of the spike: enable RepoMan with the full roster.
# Everything below the repoman.* lines is just enough Python to host the app and
# testee in a venv — the manager CLIs (copyroom/gitman/docman/repoman) come from
# the SYSTEM-WIDE toolchain venv (project 12), so there is no vendor.enable and
# no repoman.lock here.
{ ... }:

{
  repoman.enable = true;
  repoman.managers = [ "copy" "git" "test" "doc" ];
  repoman.nativeBuild = false;   # pyjutsu is resolved machine-side as a wheel

  # Python toolchain. This venv hosts the APP + testee (a uv dev dependency
  # declared in pyproject.toml) — not the manager CLIs.
  languages.python = {
    enable = true;
    version = "3.13";            # cp313-abi3 wheel floor (DESIGN §9 / README constraints)
    venv.enable = true;
    uv.enable = true;
  };
}
