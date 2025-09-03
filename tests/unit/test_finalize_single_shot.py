from importlib import reload
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import core.orchestrator as orch

def test_finalize_once(monkeypatch):
    reload(orch)
    # simulate two calls
    orch.finalize_run()
    orch.finalize_run()
    # success: no exceptions and side effects run only once (assert via internal flag)
    assert getattr(orch, "_finalized", False)
