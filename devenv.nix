{ pkgs, ... }:
let
  lisp = pkgs.sbcl.withPackages (p: [ p.check-it p.fiveam p.dexador p.yason ]);
  python = pkgs.python3.withPackages (p: [ p.pyyaml p.prompt-toolkit p.rich p.pillow p.numpy ]);
in {
  packages = [ pkgs.git lisp python pkgs.erlang pkgs.gnumake pkgs.coreutils pkgs.ffmpeg pkgs.dejavu_fonts ];
  scripts.lfe-repl.exec = ''make build && python3 scripts/repl.py --lfe "$@"'';
  scripts.test-lfe.exec = "make test";
  scripts.experiment-reverse.exec = ''python3 scripts/experiment.py "$@"'';
  scripts.image-repl.exec = ''python3 scripts/repl.py "$@"'';
  scripts.test.exec = "bash scripts/run-tests.sh test";
  scripts.test-stress.exec = ''TEST_SEED="''${TEST_SEED:-$(date +%s)}" bash scripts/run-tests.sh stress'';
  scripts.test-replay.exec = ''bash scripts/run-tests.sh replay "$@"'';
  scripts.test-live.exec = "bash scripts/run-tests.sh live";
  scripts.check-adrs.exec = "python3 scripts/check-adrs.py";
  scripts.launch-capture.exec = ''python3 scripts/launch/chat_capture.py "$@"'';
  scripts.launch-audio.exec = ''python3 scripts/launch/runway_audio.py "$@"'';
  scripts.launch-render.exec = ''python3 scripts/launch/render.py --evidence .image-agent/launch/evidence.json --audio-dir .image-agent/launch/audio --music .image-agent/launch/audio/instrumental.wav --song .image-agent/launch/audio/trailer.wav "$@"'';
  scripts.launch-package.exec = ''python3 scripts/launch/package.py "$@"'';
  scripts.test-launch.exec = ''python3 tests/launch_capture_scenarios.py && python3 tests/launch_evidence_scenarios.py && python3 scripts/launch/test_render.py && python3 scripts/launch/test_runway_audio.py'';
  enterTest = ''
    bash scripts/run-tests.sh test
    python3 scripts/check-adrs.py
    python3 tests/adr_scenarios.py
    python3 tests/cli_scenarios.py
    python3 tests/terminal_scenarios.py
  '';
}
