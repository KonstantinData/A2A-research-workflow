from agents import field_completion_agent


def _make_trigger(payload):
    return {"payload": payload, "source": "calendar"}


def test_field_completion_extracts_from_labeled_description():
    description = (
        "Agenda for kickoff meeting\n"
        "Company Name: Beispiel GmbH\n"
        "Website: HTTPS://Example.COM/path"
    )
    trigger = _make_trigger({"description": description})

    result = field_completion_agent.run(trigger)

    assert result["company_name"] == "Beispiel GmbH"
    assert result["domain"] == "example.com"


def test_field_completion_uses_extended_properties():
    trigger = _make_trigger(
        {
            "summary": "Strategy workshop",
            "extendedProperties": {
                "private": {
                    "company_label": "Future Mobility AG",
                    "company_domain": "Future-Mobility.io",
                }
            },
        }
    )

    result = field_completion_agent.run(trigger)

    assert result["company_name"] == "Future Mobility AG"
    assert result["domain"] == "future-mobility.io"
