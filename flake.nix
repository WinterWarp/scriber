{
  description = "Scriber — handwrite with a stylus to input text into GNOME apps";

  inputs.nixpkgs.url = "nixpkgs"; # resolves via the system flake registry (your nixos-unstable)

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };
      python = pkgs.python3;

      # Python with the GObject + Cairo bindings the app imports directly.
      pythonEnv = python.withPackages (ps: [ ps.pygobject3 ps.pycairo ]);

      # External binaries the app shells out to at runtime.
      #   tesseract     -> offline recognition backend
      #   wl-clipboard  -> clipboard fallback (wl-copy) when GTK clipboard is unavailable
      #   ydotool       -> optional auto-type backend (dormant unless you enable the daemon)
      runtimeTools = [ pkgs.tesseract pkgs.wl-clipboard pkgs.ydotool ];

      scriber = python.pkgs.buildPythonApplication {
        pname = "scriber";
        version = "0.1.0";
        src = ./.;
        pyproject = true;

        build-system = [ python.pkgs.setuptools ];
        dependencies = [ python.pkgs.pygobject3 python.pkgs.pycairo ];

        nativeBuildInputs = [ pkgs.wrapGAppsHook4 pkgs.gobject-introspection ];
        buildInputs = [ pkgs.gtk4 ];

        # Let buildPythonApplication's wrapper carry the GApps env (typelibs, schemas,
        # XDG_DATA_DIRS) *and* put our runtime tools on PATH, in a single wrap.
        dontWrapGApps = true;
        preFixup = ''
          makeWrapperArgs+=("''${gappsWrapperArgs[@]}" \
            --prefix PATH : ${pkgs.lib.makeBinPath runtimeTools})
        '';

        # No test phase (GUI app); import check is enough.
        doCheck = false;
        pythonImportsCheck = [ "scriber" ];

        meta = {
          description = "Handwriting-to-text input panel for GNOME (stylus friendly)";
          mainProgram = "scriber";
        };
      };
    in {
      packages.${system}.default = scriber;
      apps.${system}.default = {
        type = "app";
        program = "${scriber}/bin/scriber";
      };

      devShells.${system}.default = pkgs.mkShell {
        nativeBuildInputs = [ pkgs.wrapGAppsHook4 pkgs.gobject-introspection ];
        buildInputs = [ pythonEnv pkgs.gtk4 ] ++ runtimeTools;
        shellHook = ''
          echo "scriber dev shell — run:  python -m scriber"
        '';
      };
    };
}
