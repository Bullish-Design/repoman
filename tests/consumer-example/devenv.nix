# Consumer side of the spike: enable RepoMan with one manager.
# Everything below the two repoman.* lines is just enough Python to host the
# manager CLIs in a venv.
{ ... }:

{
  repoman.enable = true;
  repoman.managers = [ "copy" "git" "test" "doc" "session" "agent" "spec" ];
  repoman.nativeBuild = false;   # pyjutsu comes from vendomat's wheel — no Rust toolchain

  # vendomat: install pyjutsu from the prebuilt wheelhouse instead of compiling it.
  vendor.enable = true;
  vendor.libs = [ "pyjutsu" ];

  languages.python = {
    enable = true;
    version = "3.13";            # cp313-abi3 wheel floor (DESIGN §9 / README constraints)
    venv.enable = true;
    uv.enable = true;
  };
}
