# SmartThings CLI Headless OAuth Patch

## When to apply
Running `@smartthings/cli` on a headless Linux host where `open()` (browser launch) fails.

## Prerequisites
1. Resolve the compiled login-authenticator path: `npm root -g` → `node_modules/@smartthings/cli/node_modules/@smartthings/cli-lib/dist/login-authenticator.js`

## Approach A — Credentials Bridge (preferred)
Run `smartthings login` on a machine with a browser. Copy `~/.config/@smartthings/cli/credentials.json` to the headless host at the same path. Hermes reads it automatically via `auth._load_cli_credentials()`. No JS patching needed.

## Approach B — Headless URL Capture
Patch the CLI JS to write the OAuth URL to a temp file instead of opening a browser.

Find the `/start` Express route handler where `authorizeURL` is built. Before `res.redirect(...)`:
```javascript
fs_1.default.writeFileSync('/tmp/smartthings_oauth_authorize_url.txt', authorizeURL.toString() + '\n');
```

In the `server.listen` callback, replace or comment out `await open_1.default(...)` to suppress GUI launch, and log the local start URL.

After patching, run any CLI command that needs auth (e.g. `smartthings devices`). Read the OAuth URL:
```bash
cat /tmp/smartthings_oauth_authorize_url.txt
```
Open that URL in a browser that can reach the host, complete auth, and the CLI receives the callback on its local `/finish` route.

## Approach C — HTTPS Reverse Proxy via nginx
If the browser is remote and must callback over HTTPS, use nginx as a reverse proxy with a **valid** LetsEncrypt certificate. Self-signed certs cause browser warnings that break OAuth flows.

Requirements:
- A hostname with a valid SSL certificate (e.g., `ptt.tsel.la` via LetsEncrypt)
- nginx `server_name` includes both the FQDN and a local alias (e.g. `vernon`)
- nginx listens on `https://{hostname}:{port+1}` and proxies to `http://127.0.0.1:{port}`

Nginx server block (add to existing SSL vhost, e.g. `/etc/nginx/sites-enabled/ptt.tsel.la`):
```nginx
server {
    listen 61974 ssl;
    server_name ptt.tsel.la vernon;

    ssl_certificate /etc/letsencrypt/live/ptt.tsel.la/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ptt.tsel.la/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    location / {
        proxy_pass http://127.0.0.1:61973;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Then reload nginx: `sudo nginx -t && sudo systemctl reload nginx`

## Notes
- The local Express server listens on `[61973, 61974, 61975]` internally.
- Credentials are stored in `~/.config/@smartthings/cli/credentials.json`.
- Re-run `npm install -g @smartthings/cli` will overwrite any JS patches.
