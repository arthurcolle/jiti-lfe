"""Structural checks for the maintenance workflow's three documented cases."""
from pathlib import Path
import tempfile, subprocess, shutil
root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as directory:
    fixture = Path(directory)
    shutil.copytree(root / 'docs', fixture / 'docs')
    shutil.copytree(root / 'src', fixture / 'src')
    shutil.copytree(root / 'tests', fixture / 'tests')
    def validate(success=True):
        r = subprocess.run(['python3', str(root/'scripts/check-adrs.py'), str(fixture)], capture_output=True, text=True)
        assert (r.returncode == 0) == success, r.stdout + r.stderr
    # Routine fix: no invented decision, records still validate.
    before = sorted(p.name for p in (fixture/'docs/adr').glob('*.md'))
    validate()
    assert before == sorted(p.name for p in (fixture/'docs/adr').glob('*.md'))
    # Consequence correction preserves the decision and its historical rationale.
    previous = fixture/'docs/adr/0001-worker-owned-live-repair.md'
    old = previous.read_text()
    previous.write_text(old + '\nDocumented consequence: cached function objects retain their old code.\n')
    validate()
    assert old.split('## Consequences')[0] == previous.read_text().split('## Consequences')[0]
    # Changed choice requires a new record and reciprocal supersession links.
    next_id = f'{max(int(name[:4]) for name in before) + 1:04d}'
    successor_name = f'{next_id}-process-owned-repair.md'
    successor = fixture/'docs/adr'/successor_name
    successor.write_text(f'# {next_id}: Process-owned repair\n\nStatus: Proposed\nDate: 2026-10-04\n\n'
                         'Supersedes: [0001](0001-worker-owned-live-repair.md)\n\n'
                         '## Context\n\nIsolation is required.\n\n## Decision\n\nUse a process.\n\n'
                         '## Rationale\n\nThreads do not isolate crashes.\n\n## Consequences\n\nTransport is needed.\n')
    validate(False)
    previous.write_text(previous.read_text().replace('Status: Accepted','Status: Superseded') +
                        f'\nSuperseded by: [{next_id}]({successor_name})\n')
    validate()
print('ADR scenarios: routine fix, factual correction, reciprocal supersession passed')
