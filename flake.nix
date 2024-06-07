{
  description = "Sunrise clock running on raspberry pi.";

  inputs = {
    flake-utils.url = "github:numtide/flake-utils";
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    poetry2nix = {
      url = "github:nix-community/poetry2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = inputs @ {
    self,
    nixpkgs,
    flake-utils,
    poetry2nix,
  }:
    flake-utils.lib.eachDefaultSystem (system: let
      # see https://github.com/nix-community/poetry2nix/tree/master#api for more functions and examples.
      pkgs = nixpkgs.legacyPackages.${system};
      poetry2nix = inputs.poetry2nix.lib.mkPoetry2Nix {inherit pkgs;};
    in {
      packages = {
        rpiClock = poetry2nix.mkPoetryApplication {
          projectDir = self;
          overrides =
            poetry2nix.defaultPoetryOverrides.extend
            (self: super: {
              pigpio =
                super.pigpio.overridePythonAttrs
                (
                  old: {
                    buildInputs = (old.buildInputs or []) ++ [super.setuptools];
                  }
                );
              lgpio =
                super.lgpio.overridePythonAttrs
                (
                  old: {
                    buildInputs = (old.buildInputs or []) ++ [super.setuptools];
                  }
                );
            });
        };
        default = self.packages.${system}.rpiClock;
      };

      devShells.prebuilt = pkgs.mkShell {
        inputsFrom = [self.packages.${system}.rpiClock];
        packages = [pkgs.poetry];
      };

      devShells.default = pkgs.mkShell {
        packages = with pkgs; [poetry pre-commit python311];
        shellHook = ''
          pre-commit install
        '';
      };
    });
}
