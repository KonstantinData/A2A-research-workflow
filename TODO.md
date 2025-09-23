# TODO - Verbleibende Aufgaben

## 🔴 Hohe Priorität (Sicherheit)

### Cross-Site Scripting (XSS)
- [ ] **integrations/mailer.py** (Zeile 60-77): E-Mail-Body-Konstruktion sanitisieren
  - User-Input aus Event-Payloads wird ohne Sanitisierung in E-Mail eingefügt
  - HTML-Escaping implementieren falls E-Mail-Client HTML rendert

### Authorization Issues  
- [ ] **integrations/mailer.py** (Zeile 60-77): Authorization-Check verbessern
  - Client-seitige Inputs für Rollen-Validierung vermeiden
  - Server-seitige Session-Daten verwenden

### Path Traversal (verbleibend)
- [ ] **integrations/graph_storage.py** (Zeile 23-24): Pfad-Validierung hinzufügen
- [ ] **config/settings.py** (Zeile 149-154): Robustere Pfad-Validierung mit `Path.is_relative_to()`

### OS Command Injection (verbleibend)
- [ ] **agents/agent_internal_search.py** (Zeile 157-158): Unsafe Shell-Operationen ersetzen

## 🟡 Mittlere Priorität (Performance & Stabilität)

### Resource Leaks
- [ ] **core/tasks.py** (Zeile 53-54): SQLite-Connection mit `with` Statement schließen

### Error Handling
- [ ] **core/services.py** (Zeile 52-53): Spezifische Exceptions statt `Exception`
- [ ] **output/pdf_render.py** (Zeile 173-187): Logging für Exception-Handler hinzufügen
- [ ] **tests/email_smtp_test.py** (Zeile 74-76): SMTP-spezifische Exceptions verwenden

### Performance Optimierungen
- [ ] **integrations/hubspot_api.py** (Zeile 549-555): String-Operationen cachen
- [ ] **agents/reminder_service.py** (Zeile 196-205): JSONL-Parsing optimieren
- [ ] **core/autonomous_orchestrator.py** (Zeile 21-29): Lazy Agent-Initialisierung

## 🟢 Niedrige Priorität (Code Quality)

### Code-Struktur
- [ ] **core/trigger_words.py** (Zeile 143+): Funktion mit hoher Komplexität aufteilen
- [ ] **core/run_loop.py** (Zeile 154-162): Nested Function aus Loop extrahieren
- [ ] **tests/trigger_test.py** (Zeile 86-230): Lange main()-Funktion aufteilen

### Redundanzen entfernen
- [ ] **core/classify.py** (Zeile 109-110): Redundante Set-Membership-Checks
- [ ] **agents/company_data.py** (Zeile 238-239): Unnötige `list()` Calls
- [ ] **core/tasks.py** (Zeile 29-30): Doppelte Path-Konstruktion

### Dokumentation & Naming
- [ ] **tests/unit/test_email_attachments.py** (Zeile 24): Deutsche Kommentare übersetzen
- [ ] **tests/unit/test_recovery_agent.py** (Zeile 17-18): Test-Helper Naming-Convention
- [ ] **tests/unit/test_google_calendar_error_logging.py**: Duplizierte `capture` Funktion extrahieren

## 🔧 GitHub Actions & CI/CD

### Workflow Verbesserungen
- [ ] **.github/workflows/live_e2e.yml** (Zeile 49-80): Assertions durch informative Fehler ersetzen
- [ ] **.github/workflows/auto-issues.yml** (Zeile 37-106): API-Rate-Limiting implementieren
- [ ] **.github/workflows/smtp_selftest.yml** (Zeile 8-9): Hardcoded E-Mail durch Placeholder ersetzen

## 📊 Monitoring & Logging

### Logging-Verbesserungen
- [ ] **agents/agent_internal_level2_company_search.py** (Zeile 42-51): Strukturiertes Logging verwenden
- [ ] **integrations/hubspot_api.py** (Zeile 315-317): Logging für fehlende `file_id` hinzufügen

## 🧪 Test-Optimierungen

### Performance
- [ ] **tests/unit/test_internal_company_fetch.py** (Zeile 50-51): `time.sleep()` durch Mocking ersetzen
- [ ] **tests/email_imap_test.py** (Zeile 215-218): IMAP FETCH-Operationen batchen

### Code Quality
- [ ] **tests/unit/test_severity.py** (Zeile 46-47): Spezifische Exception statt `Exception`
- [ ] **tests/test_google_oauth_env_mapping.py** (Zeile 6-7): For-Loop auf mehrere Zeilen aufteilen

## 📝 Dokumentation

### Kommentare & Docs
- [ ] Alle deutschen Kommentare ins Englische übersetzen
- [ ] Fehlende Docstrings für öffentliche Funktionen hinzufügen
- [ ] API-Dokumentation für HubSpot-Integration erweitern

## ✅ Bereits erledigt

- [x] OS Command Injection in autonomen Agenten behoben
- [x] Path Traversal in trigger_words.py und settings.py behoben  
- [x] HTML Injection in pdf_render.py behoben
- [x] Performance-Optimierungen in field_completion_agent.py
- [x] Generische Exception-Handling in utils.py und email_listener.py verbessert
- [x] Ungenutzte Dateien entfernt (migrate_to_autonomous.py)
- [x] Kommentierte Code-Blöcke bereinigt
- [x] Logging-Pfade zentralisiert
- [x] Alle Unit-Tests erfolgreich (82 passed)

---

**Prioritäten-Legende:**
- 🔴 **Hoch**: Sicherheitslücken, kritische Bugs
- 🟡 **Mittel**: Performance, Stabilität, Resource-Management  
- 🟢 **Niedrig**: Code-Qualität, Wartbarkeit, Dokumentation