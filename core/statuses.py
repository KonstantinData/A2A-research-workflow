"""Workflow status definitions."""

# Final statuses indicate that no further action will occur for the event.
REPORT_SENT = "report_sent"
REPORT_NOT_SENT = "report_not_sent"
NOT_RELEVANT = "not_relevant"
ABORTED = "aborted"

FINAL_STATUSES = {REPORT_SENT, REPORT_NOT_SENT, NOT_RELEVANT, ABORTED}

# Pause statuses represent events waiting for additional information or manual action.
PENDING = "pending"
PENDING_ADMIN = "pending_admin"
NEEDS_ADMIN_FIX = "needs_admin_fix"

PAUSE_STATUSES = {PENDING, PENDING_ADMIN, NEEDS_ADMIN_FIX}
