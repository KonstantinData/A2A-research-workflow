# HubSpot Mapping Reference

Diese Datei beschreibt das Mapping vom generischen **Core‑Schema** auf die
HubSpot‑spezifischen Felder, die bei einem Upsert über `integrations/hubspot_api.py`
verwendet werden.  Der Zwei‑Schichten‑Ansatz trennt strikt zwischen
universellen Unternehmensdaten (Core) und CRM‑spezifischen Details
(HubSpot).  Das erleichtert die Wiederverwendbarkeit des Workflows
mit anderen Systemen und stellt sicher, dass nur relevante Felder
in HubSpot geschrieben werden.

## Core‑Schema

Das Core‑Schema beschreibt ein Unternehmen mit folgenden Pflichtfeldern:

| Feld | Beschreibung |
| --- | --- |
| `company_name` | Offizieller Name des Unternehmens |
| `domain` | Web‑Domain (ohne Protokoll) |
| `industry_group` | Oberes Branchencluster, z. B. „Energy“, „Healthcare“ |
| `industry` | Konkreter Geschäftsbereich, z. B. „Renewable Energy“ |
| `description` | Freitext‑Beschreibung (aus Notizen, Research) |

Optionale Felder sind `contact_info` (mit `email` und `phone`),
`country` (ISO‑3166‑Ländercode) sowie `classification` (Mapping auf WZ/NACE/ISIC).

## HubSpot‑Mapping

Beim Upsert werden die Core‑Felder wie folgt auf die HubSpot
Properties übertragen.  Zusätzlich können im `hubspot`‑Block
weitere Felder angegeben werden, um CRM‑spezifische Daten zu
speichern.

| Core‑Feld           | HubSpot Property        | Bemerkungen |
| ------------------- | ----------------------- | ----------- |
| `company_name`      | `name`                  | Firmenname |
| `domain`            | `company_domain_name`   | Primäre Domain des Unternehmens |
| `industry_group`    | `industry_group`        | Oberes Branchencluster |
| `industry`          | `industry`              | Spezifische Branche |
| `description`       | `description`           | Freitext‑Beschreibung |
| `country`           | `country`               | ISO‑3166 Länder‑Code |
| _generiert_         | `company_keywords`      | Wird automatisch aus `industry` und `description` abgeleitet, sofern nicht explizit angegeben |

### Erweiterte Felder

Der optionale `hubspot`‑Block erlaubt die Angabe weiterer CRM‑Felder.
Diese Felder spiegeln die Spalten wider, die in den bereitgestellten
Screenshots verwendet werden.  Dazu gehören unter anderem:

| HubSpot Property                 | Bedeutung |
| -------------------------------- | -------- |
| `city`                           | Ort des Firmensitzes |
| `postal_code`                    | Postleitzahl |
| `street_address`                 | Straße/Hausnummer |
| `street_address_2`               | Adresszusatz |
| `phone_number`                   | Haupttelefonnummer |
| `number_of_employees`            | Anzahl der Beschäftigten |
| `total_revenue`                  | Gesamtumsatz (als Zahl oder String) |
| `year_founded`                   | Gründungsjahr |
| `lead_status`                    | Vertriebsstatus |
| `company_owner`                  | Zuständiger Account‑Owner |
| `ideal_customer_profile_tier`    | Einstufung als ICP |
| `company_keywords`               | Schlüsselwörter (können manuell vorgegeben werden) |

Nicht alle Felder müssen gesetzt sein; fehlende Felder sollten vom
Agenten angefordert oder im CRM ergänzt werden.  Sensible oder
personenbezogene Daten (z. B. Kontaktdaten) müssen gemäß DSGVO
verarbeitet werden und dürfen nicht im Klartext in Logs oder Reports
erscheinen.