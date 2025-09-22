#!/usr/bin/env bash
set -euo pipefail
# Apply changes for 002-guardrails-event-bus
for f in agents/autonomous_report_agent.py agents/autonomous_email_agent.py agents/autonomous_research_agent.py; do
  python - <<'PY'
path = 'REPO/' + '/mnt/data/repo/A2A-research-workflow-main'
PY
done
# Copy the shim files over the originals
cp -f modernization/changes/002-guardrails-event-bus/new/agents.autonomous_report_agent.py agents/autonomous_report_agent.py
cp -f modernization/changes/002-guardrails-event-bus/new/agents.autonomous_email_agent.py agents/autonomous_email_agent.py
cp -f modernization/changes/002-guardrails-event-bus/new/agents.autonomous_research_agent.py agents/autonomous_research_agent.py
mkdir -p tests
cp -f modernization/changes/002-guardrails-event-bus/new/tests/test_legacy_agents_deprecated.py tests/test_legacy_agents_deprecated.py
echo 'Apply 002 done.'
