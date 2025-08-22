import os
from google_auth_oauthlib.flow import InstalledAppFlow

# Deine echten Google-OAuth-Daten hier einfügen:
CLIENT_ID = "HIER_CLIENT_ID_EINFÜGEN"
CLIENT_SECRET = "HIER_CLIENT_SECRET_EINFÜGEN"

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
print("\n✅ Dein refresh_token lautet:")
print(creds.refresh_token)
