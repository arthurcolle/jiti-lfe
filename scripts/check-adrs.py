#!/usr/bin/env python3
"""Validate ADR identities, local evidence links, and reciprocal supersession."""
from pathlib import Path
import re
import sys

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
records = list((root / 'docs/adr').glob('[0-9]*.md'))
errors = []
ids = {}
for path in records:
    match = re.fullmatch(r'(\d{4})-[a-z0-9-]+\.md', path.name)
    if not match:
        errors.append(f'invalid filename: {path.name}')
        continue
    if match[1] in ids:
        errors.append(f'duplicate ID: {match[1]}')
    ids[match[1]] = path
    text = path.read_text()
    if not re.search(r'^Status: (Proposed|Accepted|Superseded|Deprecated)$', text, re.M):
        errors.append(f'{path.name}: invalid status')
    if not re.search(r'^Date: \d{4}-\d{2}-\d{2}$', text, re.M):
        errors.append(f'{path.name}: missing date')
    for heading in ('Context', 'Decision', 'Rationale', 'Consequences'):
        if f'## {heading}\n' not in text:
            errors.append(f'{path.name}: missing {heading}')
    for target in re.findall(r'\]\(([^)]+)\)', text):
        if '://' not in target and not (path.parent / target.split('#')[0]).exists():
            errors.append(f'{path.name}: broken link {target}')
    for label, other_label in [('Supersedes', 'Superseded by'), ('Superseded by', 'Supersedes')]:
        for target in re.findall(r'^' + label + r': \[[^]]*\]\(([^)]+)\)', text, re.M):
            other = path.parent / target
            if not other.exists() or not re.search(r'^' + other_label + r': .*\]\(' + re.escape(path.name) + r'\)', other.read_text(), re.M):
                errors.append(f'{path.name}: nonreciprocal {label} link')
    if 'Status: Superseded' in text and 'Superseded by:' not in text:
        errors.append(f'{path.name}: missing successor')
if not records:
    errors.append('no ADR records')
if errors:
    sys.exit('\n'.join(errors))
print(f'{len(records)} ADRs: identities, evidence links, and supersession valid')
