import os
from google_auth_oauthlib.flow import InstalledAppFlow


def get_env(name: str) -> str | None:
    val = os.environ.get(name)
    return val.strip() if isinstance(val, str) else None


# 1) Zuerst echte Umgebungsvariablen lesen
CID = get_env("GOOGLE_CLIENT_ID_V2") or get_env("GOOGLE_CLIENT_ID")
CSEC = get_env("GOOGLE_CLIENT_SECRET_V2") or get_env("GOOGLE_CLIENT_SECRET")

# 2) Falls leer: optional .env nachladen (ohne Abbruch, falls nicht installiert)
if not (CID and CSEC):
    try:
        from dotenv import load_dotenv

        load_dotenv()  # lädt .env im aktuellen Ordner
        CID = CID or get_env("GOOGLE_CLIENT_ID_V2") or get_env("GOOGLE_CLIENT_ID")
        CSEC = (
            CSEC
            or get_env("GOOGLE_CLIENT_SECRET_V2")
            or get_env("GOOGLE_CLIENT_SECRET")
        )
    except Exception:
        # dotenv ist optional; wenn nicht vorhanden/fehlerhaft, machen wir unten weiter
        pass

if not CID or not CSEC:
    raise ValueError(
        "❌ GOOGLE_CLIENT_ID_V2 / GOOGLE_CLIENT_SECRET_V2 (oder Fallback GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET) sind nicht gesetzt."
    )

print(f"🔎 Verwende Client-ID (gekürzt): {CID[:10]}...")

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/contacts.readonly",
]

flow = InstalledAppFlow.from_client_config(
    {
        "installed": {
            "client_id": CID,
            "client_secret": CSEC,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    },
    scopes=SCOPES,
)

creds = flow.run_local_server(port=8888)
print("\n✅ Dein refresh_token lautet:\n")
print(creds.refresh_token)
