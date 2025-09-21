# Autonomous A2A Workflow

Das A2A-System wurde auf eine selbst-organisierende, agent-getriebene Architektur umgestellt.

## Neue Architektur

### Event-Driven System
- **Event Bus** (`core/event_bus.py`) - Zentrale Nachrichtenvermittlung
- **Agent Controller** (`core/agent_controller.py`) - Autonome Agent-Verwaltung
- **Workflow Coordinator** - Orchestriert Agent-Interaktionen

### Autonome Agents
- **Field Completion Agent** - Extrahiert fehlende Firmendaten
- **Research Agents** - Interne/externe Recherche
- **Consolidation Agent** - Zusammenführung der Ergebnisse
- **Report Agent** - PDF/CSV-Generierung
- **Email Agent** - E-Mail-Kommunikation

## Verwendung

### Autonomer Modus starten
```bash
python main_autonomous.py
```

### Web-Interface (optional)
```bash
# FastAPI installieren
pip install fastapi uvicorn

# API starten
python api/workflow_api.py
```

### Manueller Trigger
```python
from app.core.autonomous import autonomous_orchestrator

# Workflow starten
correlation_id = autonomous_orchestrator.process_manual_trigger({
    "company_name": "Example GmbH",
    "domain": "example.com",
    "creator": "user@company.com"
})

# Status prüfen
status = autonomous_orchestrator.get_workflow_status(correlation_id)
```

## Vorteile

- **Parallel Processing** - Mehrere Workflows gleichzeitig
- **Self-Organizing** - Agents koordinieren sich selbst
- **Resilient** - Fehlerbehandlung und Recovery
- **Scalable** - Neue Agents einfach hinzufügbar
- **Event-Driven** - Lose gekoppelte Komponenten

## 🧹 Bereinigte Dateien:
- `core/full_workflow.py` - Ersetzt durch autonome Agents
- `core/sources_registry.py` - Agents registrieren sich selbst
- `core/workflow_state.py` - Event Bus übernimmt State Management
- `core/task_history.py` - Event History ersetzt Task History
- `debug_*.py` - Nicht mehr benötigt

## 🔄 Migration:
```bash
python migrate_to_autonomous.py
```

## Legacy Support

Das bestehende System läuft weiterhin über `core/orchestrator.py`. 
Die autonome Version ist eine Erweiterung mit verbesserter Architektur.