from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from integrations import google_calendar


def test_normalize_extracts_company_and_domain():
    ev = {
        "id": "1",
        "summary": "Weekly sync",
        "description": "ACME GmbH kickoff at acme.com",
    }
    norm = google_calendar._normalize(ev, "primary")
    assert norm["company_name"] == "ACME GmbH"
    assert norm["domain"] == "acme.com"
