# Config

## Purpose

Configuration files for the A2A research workflow.

## Files

- `trigger_words.txt`: Newline-separated trigger words or phrases (case-insensitive) used to identify relevant content in documents.

## Dependencies

None.

## Usage

Set the `TRIGGER_WORDS_FILE` environment variable to override the default path to `trigger_words.txt`.

Example in Bash:

```bash
export TRIGGER_WORDS_FILE=/path/to/custom_trigger_words.txt
```
