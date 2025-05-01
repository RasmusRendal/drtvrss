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
      pythonEnv = pkgs.python3.withPackages (p: with p; [flask flask-caching aiohttp gunicorn pylint] ++ p.flask.optional-dependencies.async);
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
            base_url = mkOption {
              description = "Base URL of the service";
              default = null;
              type = types.str;
            };
            service_name = mkOption {
              description = "Service Name";
              default = "Public Service";
              type = types.str;
            };
            recommended_shows = mkOption {
              description = "Shows that should populate the cache initially";
              default = [];
              type = types.listOf types.str;
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
              environment.BASE_URL = config.services.drtvrss.base_url;
              environment.RECOMMENDED_SHOWS = let
                join = d: l:
                  if pkgs.lib.length l == 0
                  then builtins.elemAt l 0
                  else pkgs.lib.lists.foldl (a: b: a + d + b) (builtins.elemAt l 0) (pkgs.lib.lists.tail l);
              in
                join ":" config.services.drtvrss.recommended_shows;
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
