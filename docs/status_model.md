# Status Model

Dieser Workflow verwendet klar definierte Statuswerte, um den Fortschritt eines Triggers nachzuvollziehen.

## Final Statuses
Diese Stati markieren einen abgeschlossenen Vorgang:

- `report_sent`
- `report_not_sent`
- `not_relevant`
- `aborted`

## Pause Statuses
Diese Stati zeigen an, dass ein Trigger vorübergehend angehalten ist und weitere Eingaben oder manuelle Eingriffe erfordert:

- `pending`
- `pending_admin`
- `needs_admin_fix`

Die Sets `FINAL_STATUSES` und `PAUSE_STATUSES` sind in `core/statuses.py` definiert und werden vor dem Schreiben entsprechender Logeinträge importiert.
