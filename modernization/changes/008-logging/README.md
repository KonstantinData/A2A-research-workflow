# Changeset 008 – Structured Logging

This changeset introduces structured logging for both JavaScript and Python components.

* Installs the `pino` package and adds it to `package.json`.
* Updates `answer.js` to create a `pino` logger and emit informational messages before and after generating the presentation.
* Configures Python’s built-in logging in `create_montage.py`, logs the number of images being combined, and logs when the montage file is written.  Errors during montage creation are logged and re-raised.

Rollback: Remove `pino` from `package.json`, revert changes in `answer.js` and `create_montage.py` to remove logging.