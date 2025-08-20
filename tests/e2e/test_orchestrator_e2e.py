"""End-to-end test for running the orchestrator CLI."""

import os
import subprocess
from pathlib import Path


def test_orchestrator_cli(tmp_path):
    env = os.environ.copy()
    env["USE_PUSH_TRIGGERS"] = "1"
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
    script = Path(__file__).resolve().parents[2] / "core" / "orchestrator.py"
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
    assert (out_dir / "report.pdf").exists()
    assert (out_dir / "data.csv").exists()
