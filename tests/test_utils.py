from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from integrations.google_calendar import contains_trigger


def test_contains_trigger_case_insensitive():
    assert contains_trigger({"summary": "Meeting-Vorbereitung Dr. Willmar"}, ["meeting-vorbereitung"])


def test_contains_trigger_unicode_dash():
    assert contains_trigger({"summary": "Meeting–Vorbereitung"}, ["meeting-vorbereitung"])


def test_contains_trigger_compound():
    assert contains_trigger({"summary": "Terminvorbereitung für Kunde XY"}, ["terminvorbereitung"])


def test_contains_trigger_umlaut():
    assert contains_trigger({"summary": "Kundenrecherche Schäfer"}, ["schaefer"])


def test_contains_trigger_nonbreaking_hyphen():
    event_title = "Meeting‑Vorbereitung Dr. Willmar Schwabe"
    triggers = ["meeting-vorbereitung"]
    assert contains_trigger({"summary": event_title}, triggers)


def test_contains_trigger_em_dash():
    event_title = "Meeting—Vorbereitung"
    triggers = ["meeting-vorbereitung"]
    assert contains_trigger({"summary": event_title}, triggers)
