import os
from google_auth_oauthlib.flow import InstalledAppFlow

# Secrets direkt aus Umgebungsvariablen lesen
CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")

if not CLIENT_ID or not CLIENT_SECRET:
    raise ValueError(
        "❌ GOOGLE_CLIENT_ID oder GOOGLE_CLIENT_SECRET fehlt in den Umgebungsvariablen."
    )

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/contacts.readonly",
]

flow = InstalledAppFlow.from_client_config(
    {
        "installed": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    },
    scopes=SCOPES,
)

creds = flow.run_local_server(port=8080)
print("\n✅ Dein refresh_token lautet:\n")
print(creds.refresh_token)
