import os
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

# 🔄 .env laden
load_dotenv()

# ✅ Scopes – hier beide, wie bei deiner OAuth-Zustimmung
SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/contacts.readonly",
]


# 🔍 Hilfsfunktion für Status-Checks
def check_env_vars():
    missing = []
    for key in [
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
        "GOOGLE_REFRESH_TOKEN",
        "GOOGLE_TOKEN_URI",
    ]:
        if not os.getenv(key):
            missing.append(key)
    return missing


# ✅ Schritt 1: .env prüfen
missing_vars = check_env_vars()
if missing_vars:
    print("❌ Fehlende Umgebungsvariablen:", ", ".join(missing_vars))
    exit(1)

# ✅ Schritt 2: Credentials laden
creds = Credentials(
    None,
    refresh_token=os.getenv("GOOGLE_REFRESH_TOKEN"),
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    token_uri=os.getenv("GOOGLE_TOKEN_URI"),
    scopes=SCOPES,
)

# ✅ Schritt 3: Token ggf. auffrischen
try:
    print("🔐 Versuche Zugriff mit Refresh Token...")
    creds.refresh(Request())
    print("✅ Token erfolgreich aktualisiert.")

    # ✅ Schritt 4: Google Calendar testen
    service = build("calendar", "v3", credentials=creds)
    calendars = service.calendarList().list().execute()

    print("📅 Zugriff auf Google Calendar erfolgreich!")
    print("Gefundene Kalender:")
    for cal in calendars.get("items", []):
        print(" -", cal["summary"])

except Exception as e:
    print("❌ Fehler beim Zugriff auf Google Calendar:")
    print(e)
