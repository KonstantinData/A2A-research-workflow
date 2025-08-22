import os
from google_auth_oauthlib.flow import InstalledAppFlow

# 1) Erst V2-Variablen versuchen, dann Fallback
CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID_V2") or os.environ.get("GOOGLE_CLIENT_ID")
CLIENT_SEC = os.environ.get("GOOGLE_CLIENT_SECRET_V2") or os.environ.get(
    "GOOGLE_CLIENT_SECRET"
)

if not CLIENT_ID or not CLIENT_SEC:
    raise ValueError(
        "❌ GOOGLE_CLIENT_ID_V2 / GOOGLE_CLIENT_SECRET_V2 (oder Fallback GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET) sind nicht gesetzt."
    )

print(f"🔎 Verwende Client-ID: {CLIENT_ID[:8]}...apps.googleusercontent.com")

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/contacts.readonly",
]

flow = InstalledAppFlow.from_client_config(
    {
        "installed": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SEC,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    },
    scopes=SCOPES,
)

# Port auf 8888 lassen (bei dir hat das geklappt)
creds = flow.run_local_server(port=8888)

print("\n✅ Dein refresh_token lautet:\n")
print(creds.refresh_token)
