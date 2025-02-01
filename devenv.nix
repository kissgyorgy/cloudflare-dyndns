{ pkgs, lib, config, inputs, ... }:
{
  env = {
    UV_PYTHON_DOWNLOADS = "never";
    CURRENT_VERSION = "v" + (builtins.fromTOML (builtins.readFile ./pyproject.toml)).project.version;
  };

  # https://devenv.sh/packages/
  packages = with pkgs; [ just podman ];

  # https://devenv.sh/languages/
  languages.python = {
    enable = true;
    uv = {
      enable = true;
      sync.enable = true;
    };
  };

  # https://devenv.sh/tests/
  enterTest = "python -m pytest";

  # https://devenv.sh/pre-commit-hooks/
  pre-commit.default_stages = [ "pre-push" "manual" ];
  pre-commit.hooks = {
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
  };
  # See full reference at https://devenv.sh/reference/options/
}
