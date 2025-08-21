
# Logging

## Purpose

Logging utilities and error definitions.

## Files

- `logger.py`: Emits structured JSON logs via the standard Python logging module.
- `errors.py`: Custom error classes, including support for GitHub issue creation.

## Dependencies

- `requests` (used in `errors.py` for GitHub API integration)

## Usage

- Use `logger.get_logger()` to obtain a structured logger.
- Raise `SoftFailError` or `HardFailError` from `errors` to indicate expected or critical issues.

Example:

```python
from logging.logger import get_logger
from logging.errors import HardFailError

log = get_logger(run_id="abc123", stage="fetch")
log.info("Start fetching contacts")

raise HardFailError("Google API credentials missing")
```
