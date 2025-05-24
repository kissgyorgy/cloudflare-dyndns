{
  description = "CloudFlare DynDNS";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-25.05";
  };

  outputs = { self, nixpkgs }:
    let
      supportedSystems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];
      forAllSystems = nixpkgs.lib.genAttrs supportedSystems;
      name = "cloudflare-dyndns";
    in
    {
      packages = forAllSystems (system:
        let
          pkgs = import nixpkgs { inherit system; };
        in
        {
          default = with pkgs.python312Packages; buildPythonApplication {
            pname = name;
            version = "5.4";
            pyproject = true;
            src = ./.;
            dependencies = [
              click
              httpx
              truststore
              pydantic
            ];
            build-system = [
              hatchling
            ];
            meta.mainProgram = name;
          };
        }
      );
    };
}
