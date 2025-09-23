#!/usr/bin/env python3
import json
import pathlib
import re
import sys

root = pathlib.Path('.')
plan = json.loads((root / 'modernization/plan.json').read_text(encoding='utf-8'))
adrs = {
    p.name: p.read_text(encoding='utf-8')
    for p in (root / 'modernization/adr').glob('ADR-*.md')
}
problems = []
for item in plan['items']:
    adr = item.get('adr')
    if not adr or adr not in adrs:
        problems.append(f"Missing ADR for {item['id']}")
    else:
        txt = adrs[adr]
        if not re.search(r'^Status:\s*accepted\b', txt, re.IGNORECASE | re.MULTILINE):
            problems.append(f"ADR {adr} not accepted (required)")
if problems:
    print('\n'.join(problems), file=sys.stderr)
    sys.exit(1)
print('ADR consistency OK')
