"""Desktop helper for generating a Google OAuth refresh token.

The legacy "out of band" (OOB) redirect has been deprecated by Google. This
script now follows the recommended loopback redirect approach:

1. Ensure ``GOOGLE_CLIENT_ID`` and ``GOOGLE_CLIENT_SECRET`` are defined
   in your environment (``.env``).
2. Run the script. It spins up a temporary HTTP server on ``localhost:8888``
   and prints the consent URL.
3. Open the printed URL in your browser, grant access and wait for the redirect
   to ``http://localhost:8888``.
4. The script captures the ``code`` parameter automatically and exchanges it
   for tokens.
"""

from __future__ import annotations

import http.server
import json
import threading
import urllib.parse

import requests
from dotenv import load_dotenv

from config.settings import Settings


AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
REDIRECT_PORT = 8888
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/"

# Calendar scopes required by the workflow. Adjust if the project
# scope changes.
SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
]


class OAuthState:
    """Shared state for the temporary OAuth callback server."""

    code: str | None = None
    error: str | None = None
    event = threading.Event()


class OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    """Minimal HTTP handler that captures the OAuth authorization code."""

    def do_GET(self) -> None:  # noqa: N802 (framework signature)
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        message = "No authorization code found."
        if "code" in params:
            OAuthState.code = params["code"][0]
            message = "Authorization complete. You can close this tab."  # pragma: no cover - user flow
        elif "error" in params:
            OAuthState.error = params["error"][0]
            message = f"Authorization failed: {OAuthState.error}"  # pragma: no cover - user flow

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            f"<html><body><p>{message}</p></body></html>".encode("utf-8")
        )
        OAuthState.event.set()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003, D401
        """Silence default request logging."""

        return


def start_callback_server() -> threading.Thread:
    """Start the temporary HTTP server in a background thread."""

    OAuthState.code = None
    OAuthState.error = None
    OAuthState.event.clear()

    server = http.server.HTTPServer(("localhost", REDIRECT_PORT), OAuthCallbackHandler)
    server.timeout = 1

    def _serve() -> None:
        with server:
            while not OAuthState.event.is_set():
                server.handle_request()

    thread = threading.Thread(target=_serve, daemon=True)
    thread.start()
    return thread


def build_auth_url(client_id: str) -> str:
    """Construct the Google authorization URL."""

    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"{AUTH_ENDPOINT}?{urllib.parse.urlencode(params, quote_via=urllib.parse.quote)}"


def exchange_code_for_tokens(client_id: str, client_secret: str, code: str) -> dict:
    """Exchange the authorization code for tokens."""

    data = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    response = requests.post(TOKEN_ENDPOINT, data=data, timeout=30)
    response.raise_for_status()
    return response.json()


def main() -> None:
    load_dotenv()

    settings = Settings()
    client_id = settings.google_client_id
    client_secret = settings.google_client_secret
    if not client_id or not client_secret:
        raise SystemExit(
            "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set in the environment/.env file."
        )

    server_thread = start_callback_server()
    auth_url = build_auth_url(client_id)
    print("Open the following URL in your browser to authorize access:\n")
    print(auth_url)
    print("\nWaiting for the redirect to complete...")

    try:
        OAuthState.event.wait()
    except KeyboardInterrupt:  # pragma: no cover - manual usage
        raise SystemExit("Aborted by user.")

    server_thread.join(timeout=2)

    if OAuthState.error:
        raise SystemExit(f"Authorization failed: {OAuthState.error}")

    auth_code = OAuthState.code
    if not auth_code:
        raise SystemExit("No authorization code received.")

    tokens = exchange_code_for_tokens(client_id, client_secret, auth_code)
    print("\nToken response:\n")
    print(json.dumps(tokens, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
