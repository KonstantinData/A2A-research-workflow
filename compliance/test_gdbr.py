from compliance.gdpr import anonymize

test_data = {
    "name": "Alice",
    "email": "alice@example.com",
    "notes": "Call her at +49 123 4567890 or email bob@example.org",
    "nested": {"address": "Main St 123", "message": "Contact: test@mail.com"},
}

cleaned = anonymize(test_data)
print(cleaned)
