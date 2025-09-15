# Core

## Purpose
Core orchestration and helper modules that coordinate the overall workflow.

## Files
- `orchestrator.py`: entry point for the workflow.
- `consolidate.py`: merge data from agents.
- `classify.py`: assign industry codes and tags.
- `duplicate_check.py`: basic duplicate detection.
- `sources_registry.py`: canonical list of research sources.
- `trigger_words.py`: load and match trigger words.

## Dependencies
Standard Python libraries only in this skeleton.

## Usage
The orchestrator coordinates agents, consolidation, duplicate detection, rendering, and notifications; invoke with `python -m core.orchestrator`.

## Documentation
- [Status model](../docs/status_model.md)
