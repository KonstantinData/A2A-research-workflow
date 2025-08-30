from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from integrations.google_calendar import contains_trigger


def test_contains_trigger_true():
    assert contains_trigger("Besuchsvorbereitung mit Kunde")


def test_contains_trigger_false():
    assert not contains_trigger("Irrelevantes Meeting")

