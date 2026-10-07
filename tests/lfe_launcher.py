#!/usr/bin/env python3
"""Verify actual LFE defaults and explicit backend routing without an SBCL install."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / 'scripts/repl.py'


def run(path, arguments):
    return subprocess.run([sys.executable, '-B', str(path), *arguments],
                          cwd=ROOT, text=True, capture_output=True, timeout=20)


with tempfile.TemporaryDirectory(prefix='jiti-launcher-') as temporary:
    directory = Path(temporary)
    for flags, name in [([], 'default'), (['--lfe'], 'explicit')]:
        result = run(LAUNCHER, [*flags, '--store', str(directory/name), '--eval', "(state-put 'launcher-proof (+ 2 3))", '--json'])
        assert result.returncode == 0, result.stdout + result.stderr
        receipt = next(item for item in map(json.loads, result.stdout.splitlines()) if item.get('value') == '5')
        assert receipt['status'] == 'ok' and receipt['value'] == '5', receipt
        assert (directory/name/'CURRENT').exists(), 'Default must publish an LFE store'
    # Use the identical launcher with routing probes; legacy evaluation is tested
    # separately by the SBCL suite, not inferred from this dispatch assertion.
    probe = directory/'probe'
    probe.mkdir()
    shutil.copyfile(LAUNCHER, probe/'repl.py')
    (probe/'lfe_repl.py').write_text(
        'import json\ndef main(args):\n    print(json.dumps({"backend": "lfe", "args": args})); return 0\n')
    (probe/'legacy_repl.py').write_text(
        'import json, sys\nprint(json.dumps({"backend": "sbcl", "args": sys.argv[1:]}))\n')
    for flags, backend in [([], 'lfe'), (['--lfe'], 'lfe'), (['--legacy'], 'sbcl')]:
        result = run(probe/'repl.py', [*flags, '--store', 'unchanged', '--plain'])
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout) == {'backend': backend, 'args': ['--store', 'unchanged', '--plain']}
    result = run(probe/'repl.py', ['--legacy', '--lfe'])
    assert result.returncode != 0 and not result.stdout and 'choose one' in result.stderr
    assert 'scripts/repl.py --legacy' in (ROOT/'devenv.nix').read_text()
print('PASS: actual LFE default, compatible --lfe, explicit legacy routing, conflicting selectors')
