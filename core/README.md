
# Core

## Purpose

Core orchestration and helper modules that coordinate the overall workflow.

## Files

- `orchestrator.py`: Entry point for the workflow.
- `consolidate.py`: Merge data from agents.
- `classify.py`: Assign industry codes and tags.
- `duplicate_check.py`: Basic duplicate detection.
- `feature_flags.py`: Toggles for optional features.
- `trigger_words.py`: Load and match trigger words.

## Dependencies

Standard Python libraries only in this skeleton.

## Usage

The orchestrator coordinates agents, consolidation, rendering, and notifications.
You can invoke it directly using:

```bash
python -m core.orchestrator
```
