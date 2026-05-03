"""SmartThings OAuth 2.0 + PAT authentication manager."""
import json, os, time, webbrowser, secrets, http.server, socketserver, threading, urllib.parse
from typing import Optional
import requests

AUTH_FILE = os.path.expanduser("~/.hermes/smartthings_auth.json")
OAUTH_AUTH_URL = "https://api.smartthings.com/oauth/authorize"
OAUTH_TOKEN_URL = "https://api.smartthings.com/oauth/token"


def _load_auth() -> dict:
    if os.path.exists(AUTH_FILE):
        try:
            with open(AUTH_FILE) as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}


def _save_auth(data: dict):
    os.makedirs(os.path.dirname(AUTH_FILE), exist_ok=True)
    with open(AUTH_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_token() -> str | None:
    """Return a valid access token (PAT or OAuth), or None."""
    auth = _load_auth()
    # 1. Check PAT (simplest, but may be short-lived now)
    pat = os.getenv("SMARTTHINGS_TOKEN")
    if pat:
        return pat

    # 2. Check OAuth tokens
    oauth = auth.get("oauth", {})
    access = oauth.get("access_token")
    if not access:
        return None
    # 3. Refresh if expired or within 10 min buffer
    expires_at = oauth.get("expires_at", 0)
    if time.time() + 600 >= expires_at:
        refresh = oauth.get("refresh_token")
        if refresh:
            new = _do_refresh(refresh, oauth.get("client_id"), oauth.get("client_secret"))
            if new:
                return new["access_token"]
        return None
    return access


def _do_refresh(refresh_token: str, client_id: str, client_secret: str) -> dict | None:
    """Exchange refresh token for new access token."""
    resp = requests.post(
        OAUTH_TOKEN_URL,
        auth=(client_id, client_secret),
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=(7, 15),
    )
    if not resp.ok:
        return None
    data = resp.json()
    access = data.get("access_token")
    if not access:
        return None
    expires_in = data.get("expires_in", 86400)
    record = {
        "access_token": access,
        "refresh_token": data.get("refresh_token") or refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
        "expires_at": int(time.time() + expires_in),
    }
    _save_auth({"oauth": record})
    return record


def start_oauth_flow(client_id: str, client_secret: str, redirect_port: int = 0) -> str | None:
    """Start local OAuth authorization-code flow and return access token.
    
    Uses ephemeral localhost redirect. Call this when no valid token exists.
    Requires user interaction (browser open + login + authorize).
    """
    state = secrets.token_urlsafe(16)
    code_holder = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            if "code" in qs:
                code_holder["code"] = qs["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h1>SmartThings auth successful</h1><p>You can close this window.</p>")
            elif "error" in qs:
                code_holder["error"] = qs["error"][0]
                self.send_response(400)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(f"<h1>Error: {qs['error'][0]}</h1>".encode())
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            pass  # silence server logs

    with socketserver.TCPServer(("127.0.0.1", redirect_port), Handler) as srv:
        port = srv.server_address[1]
        redirect_uri = f"http://127.0.0.1:{port}/callback"
        auth_url = (
            f"{OAUTH_AUTH_URL}?"
            f"response_type=code&"
            f"client_id={client_id}&"
            f"redirect_uri={urllib.parse.quote(redirect_uri, safe='')}&"
            f"scope={urllib.parse.quote('r:devices:* w:devices:* r:locations:* w:locations:* r:rules:* w:rules:*', safe='')}&"
            f"state={state}"
        )
        # Start server in background
        thread = threading.Thread(target=srv.handle_request, daemon=True)
        thread.start()
        # Open browser
        webbrowser.open(auth_url)
        
        # Wait for callback (max 5 min)
        thread.join(timeout=300)

    code = code_holder.get("code")
    if not code:
        return None

    # Exchange code for tokens
    resp = requests.post(
        OAUTH_TOKEN_URL,
        auth=(client_id, client_secret),
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=(7, 15),
    )
    if not resp.ok:
        return None
    data = resp.json()
    access = data.get("access_token")
    if not access:
        return None
    expires_in = data.get("expires_in", 86400)
    record = {
        "access_token": access,
        "refresh_token": data.get("refresh_token", ""),
        "client_id": client_id,
        "client_secret": client_secret,
        "expires_at": int(time.time() + expires_in),
    }
    _save_auth({"oauth": record})
    return access


def reset_auth():
    """Clear stored OAuth tokens. Next call will require re-auth or PAT."""
    if os.path.exists(AUTH_FILE):
        os.remove(AUTH_FILE)
