#!/usr/bin/env python3
import re, sys
from pathlib import Path
SCAN = {'.py','.j2','.html','.txt','.yaml','.yml','.json','.ini','.cfg'}
RX = [re.compile(p, re.I) for p in [r"\bDE" "MO\b", "place" + "holder", "lorem" + " ipsum"]]
bad = []
for p in Path('.').rglob('*'):
    if p.is_file() and p.suffix in SCAN:
        t = p.read_text(errors='ignore')
        if any(rx.search(t) for rx in RX):
            bad.append(str(p))
if bad:
    print("❌ " + "Place" "holder/" + "de" "mo strings found:\n" + "\n".join(sorted(set(bad))))
    sys.exit(1)
print("✅ No " + "place" "holder/" + "de" "mo strings detected.")
