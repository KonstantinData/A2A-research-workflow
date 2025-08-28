import yaml
from pathlib import Path

def test_ci_cd_workflow_yaml_valid():
    path = Path('.github/workflows/ci_cd.yml')
    with path.open('r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    assert isinstance(data, dict)
