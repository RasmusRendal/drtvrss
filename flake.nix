{
  inputs = {
    nixpkgs.url = "nixpkgs/nixos-24.11";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = {
    self,
    flake-utils,
    nixpkgs,
    ...
  }:
    flake-utils.lib.eachDefaultSystem (system: let
      pkgs = import nixpkgs {inherit system;};
      pythonEnv = pkgs.python3.withPackages (p: with p; [flask flask-caching requests beautifulsoup4 gunicorn]);
    in rec {
      devShells.default = pkgs.mkShell {
        buildInputs = [pythonEnv];
      };
      nixosModules.default = {config, ...}:
        with pkgs.lib; {
          options.services.drtvrss = {
            enable = mkEnableOption "drtvrss service";
            host = mkOption {
              description = "DRTVRSS host";
              default = "127.0.0.1:8125";
              type = types.str;
            };
          };
          config = mkIf config.services.drtvrss.enable {
            systemd.services.drtvrss = let
              servsrc = pkgs.writeTextFile {
                name = "drtvrss";
                text = builtins.readFile ./drtvrss.py;
                destination = "/drtvrss.py";
              };
            in {
              enable = true;
              confinement.enable = true;
              after = ["network.target"];
              wantedBy = ["multi-user.target"];
              serviceConfig = {
                DynamicUser = true;
                Restart = "always";
              };

              script = "${pythonEnv}/bin/gunicorn -b ${config.services.drtvrss.host} --pythonpath ${servsrc} drtvrss:app";
            };
          };
        };
    });
}
