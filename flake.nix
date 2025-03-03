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
      pythonEnv = pkgs.python3.withPackages (p: with p; [flask flask-caching requests gunicorn pylint]);
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
            klagemail = mkOption {
              description = "Complaints E-mail";
              default = null;
              type = types.str;
            };
            service_name = mkOption {
              description = "Service Name";
              default = "Public Service";
              type = types.str;
            };
          };
          config = mkIf config.services.drtvrss.enable {
            systemd.services.drtvrss = let
              servsrc = pkgs.stdenvNoCC.mkDerivation {
                name = "drtvrss";
                src = ./.;
                buildPhase = ''
                  mkdir -p $out;
                  cp -R ./* $out/
                '';
              };
            in {
              enable = true;
              confinement.enable = true;
              after = ["network.target"];
              wantedBy = ["multi-user.target"];
              environment.KLAGE_MAIL = config.services.drtvrss.klagemail;
              environment.SERVICE_NAME = config.services.drtvrss.service_name;
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
