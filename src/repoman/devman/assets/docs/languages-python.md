# languages.python — enable / version / venv / uv

## Options

    languages.python = {
      enable = true;
      version = "3.12";          # requires the `nixpkgs-python` input (see inputs-and-imports.md)
      venv.enable = true;        # creates a venv, puts it on PATH
      uv.enable = true;          # provides uv for dependency management
    };

## The venv gotcha

`venv.enable = true` **creates** a venv but does **not** install your project's dependencies. Until
a sync runs, `import yourpkg` / third-party imports raise `ModuleNotFoundError`:

    devenv shell -- uv sync --all-extras      # install deps into the venv
    devenv shell -- uv pip install -e .       # editable install of the project itself

(Trigger + recovery: the `devenv-python-venv` skill.)

## Version pinning

`version = "3.12"` only resolves when the **`nixpkgs-python`** input is declared in `devenv.yaml`.
Without it the pin is silently ineffective. See `inputs-and-imports.md`.

## Running Python

Always through the shell so it uses *this* venv and interpreter:

    devenv shell -- python -c 'import sys; print(sys.executable)'
