from __future__ import annotations

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import SETTINGS


@pytest.fixture(autouse=True)
def _temporary_settings_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    original = {
        "root_dir": SETTINGS.root_dir,
        "logs_dir": SETTINGS.logs_dir,
        "workflows_dir": SETTINGS.workflows_dir,
        "output_dir": SETTINGS.output_dir,
        "exports_dir": SETTINGS.exports_dir,
        "artifacts_dir": SETTINGS.artifacts_dir,
    }

    monkeypatch.setattr(SETTINGS, "root_dir", tmp_path)
    monkeypatch.setattr(SETTINGS, "logs_dir", tmp_path / "logs")
    monkeypatch.setattr(SETTINGS, "workflows_dir", tmp_path / "logs" / "workflows")
    monkeypatch.setattr(SETTINGS, "output_dir", tmp_path / "output")
    monkeypatch.setattr(SETTINGS, "exports_dir", tmp_path / "output" / "exports")
    monkeypatch.setattr(SETTINGS, "artifacts_dir", tmp_path / "artifacts")

    yield

    for key, value in original.items():
        setattr(SETTINGS, key, value)


@pytest.fixture
def company_acme():
    return {"name": "Acme GmbH", "website": "https://acme.example"}


@pytest.fixture
def company_globex():
    return {"name": "Globex Corp", "website": "https://globex.example"}


@pytest.fixture
def company_initech():
    return {"name": "Initech", "website": "https://initech.example"}


@pytest.fixture
def company_umbrella():
    return {"name": "Umbrella Corp", "website": "https://umbrella.example"}


@pytest.fixture
def company_vehement():
    return {"name": "Vehement Capital Partners", "website": "https://vehement.example"}


@pytest.fixture
def sample_companies(company_acme, company_globex, company_initech, company_umbrella, company_vehement):
    return [
        company_acme,
        company_globex,
        company_initech,
        company_umbrella,
        company_vehement,
    ]
