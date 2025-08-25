"""End-to-end test for running the orchestrator CLI."""

import os
import subprocess
from pathlib import Path


def test_orchestrator_cli(tmp_path):
    # Provide a stub email_sender module so the CLI doesn't attempt real SMTP.
    stub_pkg = tmp_path / "integrations"
    stub_pkg.mkdir(parents=True)
    # Namespace package: no __init__.py so existing modules remain visible.
    (stub_pkg / "email_sender.py").write_text("def send_email(*a, **k):\n    pass\n")

    env = os.environ.copy()
    env["USE_PUSH_TRIGGERS"] = "1"
    # Prepend stub package to PYTHONPATH so it shadows the real module.
    repo_root = Path(__file__).resolve().parents[2]
    env["PYTHONPATH"] = f"{tmp_path}:{repo_root}"
    script = repo_root / "core" / "orchestrator.py"
    cmd = [
        "python",
        str(script),
        "--company",
        "Acme GmbH",
        "--website",
        "https://acme.example",
    ]
    subprocess.run(cmd, cwd=tmp_path, env=env, check=True)

    out_dir = Path(tmp_path) / "output/exports"
    assert not (out_dir / "report.pdf").exists()
    assert not (out_dir / "data.csv").exists()
    log_files = list((Path(tmp_path) / "logs" / "workflows").glob("*_workflow.jsonl"))
    assert log_files, "log file missing"
    assert '"status": "no_triggers"' in log_files[0].read_text()
