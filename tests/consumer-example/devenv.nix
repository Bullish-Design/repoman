# Consumer side of the spike: enable RepoMan with one manager.
# Everything below the two repoman.* lines is just enough Python to host the
# manager CLIs in a venv.
{ ... }:

{
  repoman.enable = true;
  repoman.managers = [ "copy" "git" "test" "session" "agent" ];

  languages.python = {
    enable = true;
    venv.enable = true;
    uv.enable = true;
  };
}
