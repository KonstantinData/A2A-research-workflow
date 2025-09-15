# Config

## Purpose
Configuration files for the workflow.

## Files
- `settings.py`: centralised runtime configuration and feature flags loaded from environment variables.
- `trigger_words.txt`: newline-separated trigger words or phrases (case-insensitive).

## Dependencies
None.

## Usage
Set the `TRIGGER_WORDS_FILE` environment variable to override the default location.
