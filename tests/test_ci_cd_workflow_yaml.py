from pathlib import Path
import pytest

try:
    import yaml
except Exception:  # pragma: no cover - optional dependency for test
    yaml = None

def test_ci_cd_workflow_yaml_valid():
    if yaml is None:
        pytest.skip("pyyaml not installed")
    path = Path('.github/workflows/ci_cd.yml')
    with path.open('r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    assert isinstance(data, dict)
