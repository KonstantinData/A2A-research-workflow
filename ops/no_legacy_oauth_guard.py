#!/usr/bin/env python3
import sys, re
from pathlib import Path
rx = re.compile(r"GOOGLE_CLIENT_(?:ID|SECRET)_V2\b|GOOGLE_(0|OAUTH_JSON|CREDENTIALS_JSON)\b")
bad = []
for p in Path('.').rglob('*'):
    if p.is_file() and p.suffix in {'.py','.md','.yaml','.yml','.env','.ini','.json','.j2','.txt','.html'}:
        if rx.search(p.read_text(errors='ignore')):
            bad.append(str(p))
if bad:
    print("❌ Legacy OAuth identifiers found:\n" + "\n".join(sorted(set(bad))))
    sys.exit(1)
print("✅ No legacy OAuth identifiers detected.")
