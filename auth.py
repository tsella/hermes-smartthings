"""SmartThings OAuth 2.0 + PAT authentication manager."""
import json, os, time, webbrowser, secrets, http.server, socketserver, threading, urllib.parse
from pathlib import Path
import requests

from _log import get_logger

logger = get_logger(__name__)

AUTH_FILE = Path.home() / ".hermes" / "smartthings_auth.json"
CLI_CREDENTIALS_FILE = Path.home() / ".config" / "@smartthings" / "cli" / "credentials.json"
CLI_CONFIG_FILE = Path.home() / ".config" / "@smartthings" / "cli" / "config.yaml"
def _load_cli_credentials() -> dict | None:
    """Read SmartThings CLI OAuth tokens as fallback."""
    if not CLI_CREDENTIALS_FILE.exists():
        return None
    try:
        creds = json.loads(CLI_CREDENTIALS_FILE.read_text())
        default = creds.get("default", {})
        access = default.get("accessToken")
        refresh = default.get("refreshToken")
        expires_iso = default.get("expires")
        if not access:
            return None
        expires_at = 0
        if expires_iso:
            try:
                # e.g. "2026-05-04T18:56:53.631Z"
                dt = time.strptime(expires_iso.replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S.%f%z")
                expires_at = int(time.mktime(dt))
            except ValueError:
                pass
        # Read client_id from CLI config
        client_id = None
        if CLI_CONFIG_FILE.exists():
            try:
                import yaml
                cfg = yaml.safe_load(CLI_CONFIG_FILE.read_text())
                client_id = cfg.get("default", {}).get("clientIdProvider", {}).get("clientId")
            except Exception:
                pass
        record = {
            "access_token": access,
            "refresh_token": refresh,
            "client_id": client_id,
            "client_secret": None,
            "expires_at": expires_at,
        }
        logger.info("Loaded CLI credentials (expires_at=%d)", expires_at)
        return record
    except Exception as e:
        logger.warning("Failed to load CLI credentials: %s", e)
        return None


def _do_refresh_public(refresh_token: str, client_id: str | None) -> dict | None:
    """Refresh using CLI-style public client (no client_secret)."""
    logger.info("Refreshing OAuth token (public client) via %s", OAUTH_TOKEN_URL)
    try:
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        if client_id:
            data["client_id"] = client_id
        resp = requests.post(
            OAUTH_TOKEN_URL,
            data=data,
            timeout=(7, 15),
        )
        logger.debug("Refresh response status: %d", resp.status_code)
        if not resp.ok:
            logger.warning("Refresh failed: HTTP %d", resp.status_code)
            return None

        data = resp.json()
        access = data.get("access_token")
        if not access:
            logger.error("No access_token in refresh response")
            return None

        expires_in = data.get("expires_in", 86400)
        record = {
            "access_token": access,
            "refresh_token": data.get("refresh_token") or refresh_token,
            "client_id": client_id,
            "client_secret": None,
            "expires_at": int(time.time() + expires_in),
        }
        _save_auth({"oauth": record})
        logger.info("Token refresh successful (new expiry in %ds)", expires_in)
        return record
    except requests.RequestException as e:
        logger.error("Network error during refresh: %s", e)
        return None


OAUTH_AUTH_URL = "https://api.smartthings.com/oauth/authorize"
OAUTH_TOKEN_URL = "https://api.smartthings.com/oauth/token"


def _load_auth() -> dict:
    logger.debug("Loading auth from %s", AUTH_FILE)
    if AUTH_FILE.exists():
        try:
            data = json.loads(AUTH_FILE.read_text())
            logger.info("Loaded existing auth file (has_oauth=%s)", "oauth" in data)
            return data
        except json.JSONDecodeError as e:
            logger.error("Auth file corrupted: %s", e)
            return {}
    logger.info("No auth file found at %s", AUTH_FILE)
    return {}


def _save_auth(data: dict):
    logger.debug("Saving auth to %s", AUTH_FILE)
    AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    AUTH_FILE.write_text(json.dumps(data, indent=2))
    logger.info("Auth saved")


def get_token() -> str | None:
    """Return a valid access token (PAT or OAuth), or None."""
    logger.debug("Resolving SmartThings token")

    # PAT is simplest
    pat = os.getenv("SMARTTHINGS_TOKEN")
    if pat:
        logger.info("Using PAT from env var")
        return pat

    # Load OAuth
    oauth = _load_auth().get("oauth", {})
    access = oauth.get("access_token")

    # Fallback to CLI credentials if no Hermes OAuth file
    if not access:
        cli_oauth = _load_cli_credentials()
        if cli_oauth:
            oauth = cli_oauth
            access = oauth["access_token"]
            logger.info("Using OAuth tokens from CLI credentials file")

    if not access:
        logger.warning("No token found (no PAT, no saved OAuth)")
        return None

    # Not expired → use cached
    expires_at = oauth.get("expires_at", 0)
    now = time.time()
    if now + 600 < expires_at:
        logger.debug("Using cached OAuth token (expires in %ds)", int(expires_at - now))
        return access

    # Expired → refresh
    logger.info("OAuth token expired; attempting refresh")
    refresh = oauth.get("refresh_token")
    if not refresh:
        logger.error("No refresh token available")
        return None

    client_id = oauth.get("client_id")
    client_secret = oauth.get("client_secret")
    if client_secret:
        new_record = _do_refresh(refresh, client_id, client_secret)
    else:
        new_record = _do_refresh_public(refresh, client_id)
    if new_record:
        logger.info("Token refreshed successfully")
        return new_record["access_token"]

    logger.error("Token refresh failed")
    return None


def _do_refresh(refresh_token: str, client_id: str, client_secret: str) -> dict | None:
    logger.info("Refreshing OAuth token via %s", OAUTH_TOKEN_URL)
    try:
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
        logger.debug("Refresh response status: %d", resp.status_code)
        if not resp.ok:
            logger.warning("Refresh failed: HTTP %d", resp.status_code)
            return None

        data = resp.json()
        access = data.get("access_token")
        if not access:
            logger.error("No access_token in refresh response")
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
        logger.info("Token refresh successful (new expiry in %ds)", expires_in)
        return record
    except requests.RequestException as e:
        logger.error("Network error during refresh: %s", e)
        return None


def start_oauth_flow(client_id: str, client_secret: str, redirect_port: int = 0) -> str | None:
    """Run local OAuth authorization-code flow. Returns access token or None."""
    logger.info("Starting OAuth flow for client_id=%s...%s", client_id[:4], client_id[-4:] if len(client_id) > 8 else "")

    state = secrets.token_urlsafe(16)
    code_holder: dict[str, str] = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            if "code" in qs:
                code_holder["code"] = qs["code"][0]
                logger.info("OAuth callback received with auth code")
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h1>SmartThings auth successful</h1><p>You can close this window.</p>")
            elif "error" in qs:
                code_holder["error"] = qs["error"][0]
                logger.error("OAuth callback error: %s", qs["error"][0])
                self.send_response(400)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(f"<h1>Error: {qs['error'][0]}</h1>".encode())
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            pass  # silence server logs

    try:
        with socketserver.TCPServer(("127.0.0.1", redirect_port), Handler) as srv:
            port = srv.server_address[1]
            redirect_uri = f"http://127.0.0.1:{port}/callback"
            scope = "r:devices:* w:devices:* r:locations:* w:locations:* r:rules:* w:rules:*"
            auth_url = (
                f"{OAUTH_AUTH_URL}?"
                f"response_type=code&"
                f"client_id={client_id}&"
                f"redirect_uri={urllib.parse.quote(redirect_uri, safe='')}&"
                f"scope={urllib.parse.quote(scope, safe='')}&"
                f"state={state}"
            )
            logger.info("Local callback server listening on port %d", port)
            logger.info("Opening browser for OAuth authorization...")

            thread = threading.Thread(target=srv.handle_request, daemon=True)
            thread.start()

            webbrowser.open(auth_url)
            thread.join(timeout=300)
    except OSError as e:
        logger.error("Failed to start local OAuth server: %s", e)
        return None

    if "error" in code_holder:
        logger.error("OAuth error from callback: %s", code_holder["error"])
        return None

    code = code_holder.get("code")
    if not code:
        logger.error("No auth code received from callback (timeout or user cancelled)")
        return None

    # Exchange code for tokens
    logger.info("Exchanging auth code for access token...")
    try:
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
        logger.debug("Token exchange response: HTTP %d", resp.status_code)
        if not resp.ok:
            logger.error("Token exchange failed: HTTP %d", resp.status_code)
            return None

        data = resp.json()
        access = data.get("access_token")
        if not access:
            logger.error("No access_token in token exchange response")
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
        logger.info("OAuth flow completed successfully (token expires in %ds)", expires_in)
        return access

    except requests.RequestException as e:
        logger.error("Network error during token exchange: %s", e)
        return None


def reset_auth():
    """Clear stored OAuth tokens."""
    logger.warning("Resetting stored SmartThings auth")
    if AUTH_FILE.exists():
        AUTH_FILE.unlink()
        logger.info("Deleted auth file %s", AUTH_FILE)
