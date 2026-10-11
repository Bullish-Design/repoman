# Consumer side of the spike: enable RepoMan with the full roster from
# `.repoman/project.toml`. The host profile puts the managers on PATH.
#
# Testee's module comes from the `testee` input in devenv.yaml. It declares no
# checks here, so the fixture shows the smallest consumer.
{ ... }:

{
  repoman.enable = true;

  # The venv hosts the app and check tools. The host `testee` runs the checks.
  languages.python = {
    enable = true;
    version = "3.13";            # cp313-abi3 wheel floor (DESIGN §9 / README constraints)
    venv.enable = true;
    uv.enable = true;
  };
}
