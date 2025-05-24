{
  description = "CloudFlare DynDNS";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-25.05";
  };

  outputs = { self, nixpkgs }:
    let
      lib = nixpkgs.lib;
      supportedSystems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];
      forAllSystems = lib.genAttrs supportedSystems;
      meta = (import ./meta.nix) lib;
    in
    {
      packages = forAllSystems (system:
        let
          pkgs = import nixpkgs { inherit system; };
        in
        {
          default = with pkgs.python312Packages;
            buildPythonApplication {
              pname = meta.name;
              version = meta.version;
              pyproject = true;
              src = ./.;
              dependencies = map (name: pkgs.python312Packages.${name}) meta.dependencies;
              build-system = [
                hatchling
              ];
              meta.mainProgram = meta.mainProgram;
            };
        }
      );
    };
}
