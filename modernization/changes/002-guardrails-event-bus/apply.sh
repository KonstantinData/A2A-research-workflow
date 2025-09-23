#!/usr/bin/env bash
set -euo pipefail
DRY_RUN="${DRY_RUN:-0}"
cp_or_echo() { if [ "$DRY_RUN" = "1" ]; then echo "[DRY] cp $1 $2"; else cp -f "$1" "$2"; fi; }
mkdir_or_echo() { if [ "$DRY_RUN" = "1" ]; then echo "[DRY] mkdir -p $1"; else mkdir -p "$1"; fi; }
# Apply changes for 002-guardrails-event-bus
for f in agents/autonomous_report_agent.py agents/autonomous_email_agent.py agents/autonomous_research_agent.py; do
  python - <<'PY'
path = 'REPO/' + '/mnt/data/repo/A2A-research-workflow-main'
PY
done
# Copy the shim files over the originals
cp_or_echo modernization/changes/002-guardrails-event-bus/new/agents.autonomous_report_agent.py agents/autonomous_report_agent.py
cp_or_echo modernization/changes/002-guardrails-event-bus/new/agents.autonomous_email_agent.py agents/autonomous_email_agent.py
cp_or_echo modernization/changes/002-guardrails-event-bus/new/agents.autonomous_research_agent.py agents/autonomous_research_agent.py
mkdir_or_echo tests
cp_or_echo modernization/changes/002-guardrails-event-bus/new/tests/test_legacy_agents_deprecated.py tests/test_legacy_agents_deprecated.py
echo 'Apply 002 done.'
