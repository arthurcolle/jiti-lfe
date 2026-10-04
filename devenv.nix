{ pkgs, ... }:
let
  lisp = pkgs.sbcl.withPackages (p: [ p.check-it p.fiveam p.dexador p.yason ]);
  python = pkgs.python3.withPackages (p: [ p.pyyaml ]);
in {
  packages = [ pkgs.git lisp python pkgs.coreutils ];
  scripts.image-repl.exec = ''python3 scripts/repl.py "$@"'';
  scripts.test.exec = "bash scripts/run-tests.sh test";
  scripts.test-stress.exec = ''TEST_SEED="''${TEST_SEED:-$(date +%s)}" bash scripts/run-tests.sh stress'';
  scripts.test-replay.exec = ''bash scripts/run-tests.sh replay "$@"'';
  scripts.test-live.exec = "bash scripts/run-tests.sh live";
  scripts.check-adrs.exec = "python3 scripts/check-adrs.py";
  enterTest = ''
    bash scripts/run-tests.sh test
    python3 scripts/check-adrs.py
    python3 tests/adr_scenarios.py
    python3 tests/cli_scenarios.py
  '';
}
