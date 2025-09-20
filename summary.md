# Latest Changes

## 2025-09-20
- Replaced deprecated `datetime.utcnow()` usages across calendar integrations, reminder logging, and notification logging with
  timezone-aware `datetime.now(timezone.utc)` to eliminate warnings and ensure consistent timestamps.
- Updated the event bus to execute coroutine subscribers by scheduling them on the active loop (or running them synchronously
  when no loop is available), maintaining full audit logging for async execution paths.
- Converted the autonomous workflow smoke test to use assertions instead of returning values, removing pytest warnings while
  preserving diagnostic output.
