import os
import requests
from dotenv import load_dotenv

load_dotenv()

client_id = os.getenv("GOOGLE_CLIENT_ID_V2")
client_secret = os.getenv("GOOGLE_CLIENT_SECRET_V2")

auth_code = input("Gib den Autorisierungscode ein: ").strip()

data = {
    "code": auth_code,
    "client_id": client_id,
    "client_secret": client_secret,
    "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
    "grant_type": "authorization_code",
}

response = requests.post("https://oauth2.googleapis.com/token", data=data)
response.raise_for_status()
print("Token Response:\n")
print(response.json())
