{ pkgs, config, ... }:
{
  env = {
    UV_PYTHON_DOWNLOADS = "never";
  };

  # https://devenv.sh/packages/
  packages = with pkgs; [ just ];

  # https://devenv.sh/languages/
  languages.python = {
    enable = true;
    venv.enable = true;
    uv = {
      enable = true;
      sync.enable = true;
    };
  };

  scripts.project-version = {
    exec = ''
      import tomllib
      with open("pyproject.toml", "rb") as f:
          pyproject = tomllib.load(f)
          print(pyproject["project"]["version"], end="")
    '';
    package = config.languages.python.package;
  };

  # https://devenv.sh/tests/
  enterTest = "python -m pytest";

  # https://devenv.sh/pre-commit-hooks/
  pre-commit.default_stages = [
    "pre-push"
    "manual"
  ];
  pre-commit.hooks = {
    ruff = {
      enable = true;
      args = [
        "--select"
        "I"
      ];
      excludes = [ "migrations/" ];
    };
    ruff-format.enable = true;
    check-added-large-files.enable = true;
    check-json.enable = true;
    check-toml.enable = true;
    check-yaml.enable = true;
    trim-trailing-whitespace = {
      enable = true;
      excludes = [ ".*.md$" ];
    };
    end-of-file-fixer.enable = true;
  };
  # See full reference at https://devenv.sh/reference/options/
}
