lib:
let
  project = lib.pipe ./pyproject.toml [
    builtins.readFile
    builtins.fromTOML
    (builtins.getAttr "project")
  ];
  getDepName = dep: (lib.head (lib.split "[>=<]" dep));
in
{
  inherit (project) name version;
  mainProgram = project.name;
  dependencies = map getDepName project.dependencies;
}
