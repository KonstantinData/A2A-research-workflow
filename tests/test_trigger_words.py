import pytest
from core.trigger_words import contains_trigger

TRIGGERS = ["besuchsvorbereitung", "meeting"]

def test_summary_trigger_match():
    ev = {"summary": "ACME GmbH – besuchsvorbereitung"}
    assert contains_trigger(ev, TRIGGERS)

def test_description_trigger_match():
    ev = {"description": "Weekly meeting with team"}
    assert contains_trigger(ev, TRIGGERS)

def test_location_trigger_match():
    ev = {"location": "Besprechungsraum für besuchsvorbereitung"}
    assert contains_trigger(ev, TRIGGERS)

def test_attendees_trigger_match():
    ev = {"attendees": [{"email": "meeting@acme.com"}]}
    assert contains_trigger(ev, TRIGGERS)

def test_single_typo_match():
    ev = {"summary": "ACME – besuchsvorbereitun"}  # missing 'g'
    assert contains_trigger(ev, TRIGGERS)

def test_transposition_trigger_match():
    ev = {"summary": "ACME GmbH – besuchsvorbereitugn"}  # transposition
    assert contains_trigger(ev, TRIGGERS)

def test_two_typos_fallback():
    ev = {"summary": "besuchsvorbereiitun"}  # insertion + deletion
    assert contains_trigger(ev, ["besuchsvorbereitung"])

def test_no_trigger_match():
    ev = {"summary": "Lunch with colleagues"}
    assert not contains_trigger(ev, TRIGGERS)
