
# Compliance

## Purpose

Utilities for ensuring GDPR and other compliance requirements.

## Files

- `gdpr.py`: Anonymization helpers.

## Dependencies

None.

## Usage

Import and use the `anonymize` function to remove personal data before storage or transmission.

### Example:

```python
from compliance.gdpr import anonymize

data = {
    "name": "John Doe",
    "email": "john@example.com",
    "notes": "Call at +49 123 4567890",
}

cleaned_data = anonymize(data)
print(cleaned_data)
```
