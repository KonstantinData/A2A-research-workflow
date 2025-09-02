import pytest
import pytest
from core.trigger_words import contains_trigger, load_trigger_words, suggest_similar

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


def test_suggest_similar_finds_close_trigger():
    assert suggest_similar("planning rserch tomorrow") == ["research"]


def test_customer_meeting_synonym():
    load_trigger_words.cache_clear()
    triggers = load_trigger_words()
    ev = {"summary": "Customer-Meeting with ACME"}
    assert contains_trigger(ev, triggers)


def test_custom_trigger_file(tmp_path, monkeypatch):
    fn = tmp_path / "triggers.txt"
    fn.write_text("foo\nbar baz\n")
    monkeypatch.setenv("TRIGGER_WORDS_FILE", str(fn))
    from core import trigger_words as tw
    tw.load_trigger_words.cache_clear()
    triggers = tw.load_trigger_words()
    assert {"foo", "bar baz", "bar-baz", "barbaz"}.issubset(set(triggers))
    tw.load_trigger_words.cache_clear()
