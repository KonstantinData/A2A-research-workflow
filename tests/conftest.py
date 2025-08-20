import pytest


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
