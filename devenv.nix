{ pkgs, lib, ... }:
{
  env = {
    UV_PYTHON_DOWNLOADS = "never";
    PROJECT_VERSION = (import ./meta.nix lib).version;
  };

  # https://devenv.sh/packages/
  packages = with pkgs; [
    just
    mdsh
  ];

  # https://devenv.sh/languages/
  languages.python = {
    enable = true;
    venv.enable = true;
    uv = {
      enable = true;
      sync.enable = true;
    };
  };

  # https://devenv.sh/tests/
  enterTest = "python -m pytest";

  # https://devenv.sh/pre-commit-hooks/
  git-hooks.default_stages = [
    "pre-push"
    "manual"
  ];
  git-hooks.hooks = {
    ruff = {
      enable = true;
      args = [ "--select" "I" ];
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
    cli-help-output = {
      enable = true;
      name = "Update CLI help output in README.md";
      pass_filenames = false;
      entry = "bash -c 'mdsh -i README.md 2>/dev/null'";
    };
  };
  # See full reference at https://devenv.sh/reference/options/
}
