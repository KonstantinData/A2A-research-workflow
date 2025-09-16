# Email Reply Processing

The research workflow ingests replies from the shared IMAP mailbox and
reconciles them with pending tasks.  Two components cooperate:

1. **Outbound correlation metadata** – Every reminder or missing-fields
   email sent through `integrations.email_sender` now generates a stable
   ``Message-ID`` derived from the task or event identifier.  The
   ``Message-ID`` and the associated identifiers are persisted in
   ``logs/workflows/email_reader_state.json`` via
   `integrations.email_reader.record_outbound_message()`.  This ensures
   that replies referencing the original message can be matched purely via
   the ``In-Reply-To`` or ``References`` headers.

2. **Robust IMAP ingestion** – `integrations.email_reader.fetch_replies()`
   loads the stored correlation map before polling IMAP.  Each unread
   message is matched to the correct task using the header references.  If
   headers are missing, the subject line is scanned for legacy ``Task`` or
   ``Event`` patterns as a fallback.  Processed message identifiers are
   stored in the same state file so the reader can resume after restarts
   and skip duplicates.

Additional diagnostics are appended to ``replies.jsonl`` for every
message.  The log distinguishes between successfully processed replies,
messages that did not contain structured data, and duplicates that were
skipped because their ``Message-ID`` already exists in the processed
state.

The state file contains two keys:

- ``processed_message_ids`` – sorted list of message identifiers that have
  been processed (normalised without angle brackets).
- ``correlation_index`` – mapping of normalised message identifiers to the
  latest known ``task_id`` and ``event_id`` values.

Developers can delete the state file during testing to reset the cache.
