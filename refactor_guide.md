# OAuth2-Proxy Migration Refactor Guide

This guide outlines the complete process for migrating from **HTTP Basic Authentication + IP restrictions** to a modern **OAuth2-Proxy** authentication setup. The steps below consolidate improvements and fixes identified during review.

## 1. Register a GitHub OAuth App
1. Sign in to GitHub and navigate to **Settings → Developer settings → OAuth Apps**.
2. Click **New OAuth App** and fill in:
   - **Application name**: `My Project Admin Tools` (or another name).
   - **Homepage URL**: `https://your-domain.com`.
   - **Authorization callback URLs** (one per admin subdomain):
     - `https://pgadmin.your-domain.com/oauth2/callback`
     - `https://redis.your-domain.com/oauth2/callback`
     - `https://portainer.your-domain.com/oauth2/callback`
3. Register the app, then copy the **Client ID** and generate a **Client Secret**.

## 2. Configure `.env.prod`
Append OAuth2-Proxy settings and remove obsolete IP‑whitelist variables.

```bash
# ==================================
# OAuth2-Proxy Settings
# ==================================
OAUTH2_PROXY_CLIENT_ID="YOUR_GITHUB_CLIENT_ID"
OAUTH2_PROXY_CLIENT_SECRET="YOUR_GITHUB_CLIENT_SECRET"
OAUTH2_PROXY_PROVIDER="github"

# Generate with: openssl rand -base64 32
OAUTH2_PROXY_COOKIE_SECRET="PASTE_RANDOM_STRING"
OAUTH2_PROXY_EMAIL_DOMAINS="*"                   # prefer restricting access further
#OAUTH2_PROXY_GITHUB_USER="user1,user2"         # optional: explicit GitHub usernames
#OAUTH2_PROXY_GITHUB_ORG="your-github-org"      # optional
#OAUTH2_PROXY_GITHUB_TEAMS="org/team"           # optional

OAUTH2_PROXY_SET_XAUTHREQUEST="true"
OAUTH2_PROXY_PASS_ACCESS_TOKEN="true"
OAUTH2_PROXY_HTTP_ADDRESS="http://0.0.0.0:4180"
OAUTH2_PROXY_UPSTREAMS="file:///dev/null"

# Session and cookie settings
OAUTH2_PROXY_COOKIE_EXPIRE="12h0m0s"
OAUTH2_PROXY_COOKIE_REFRESH="1h0m0s"
OAUTH2_PROXY_COOKIE_HTTPONLY="true"
OAUTH2_PROXY_COOKIE_CSRF_PER_REQUEST="true"
OAUTH2_PROXY_COOKIE_CSRF_EXPIRE="15m"

# Share a single login across all subdomains
OAUTH2_PROXY_COOKIE_DOMAINS=".your-domain.com"
OAUTH2_PROXY_COOKIE_SAMESITE="lax"
OAUTH2_PROXY_COOKIE_SECURE="true"

# Logging and health
OAUTH2_PROXY_LOGGING_FORMAT="json"
OAUTH2_PROXY_LOG_LEVEL="info"
OAUTH2_PROXY_SKIP_AUTH_REGEX="^/(health|nginx-health|ping)$"
```

Remove any variables related to the old IP restriction logic, such as `ENABLE_IP_RESTRICTION`, `ALLOWED_IP_HOME`, or similar entries.

## 3. Update `docker-compose.prod.yml`
1. Add the `oauth2_proxy` service **before** the `nginx` service:
   ```yaml
   services:
     oauth2_proxy:
       image: quay.io/oauth2-proxy/oauth2-proxy:latest
       container_name: oauth2_proxy_prod
       env_file:
         - .env.prod
       expose:
         - "4180"
       networks:
         - prodNetWork
       restart: unless-stopped
       mem_limit: 128M
       mem_reservation: 64M
      healthcheck:
        test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost:4180/ping"]
        interval: 30s
        timeout: 10s
        retries: 3
        start_period: 20s
   ```
2. Remove the htpasswd volume from `nginx`:
   ```diff
     volumes:
-      - ./nginx/htpasswd:/etc/nginx/htpasswd:ro
   ```
3. Ensure `nginx` waits for the proxy:
   ```yaml
   nginx:
     depends_on:
       - oauth2_proxy
   ```

## 4. Refactor Nginx Configuration
For each file:
- `nginx/conf/prod/portainer.conf.template`
- `nginx/conf/prod/pgadmin.conf.template`
- `nginx/conf/prod/redisinsight.conf.template`

Perform the following:
1. In the `location /` block, remove old auth and IP directives:
   ```nginx
   ${IP_RESTRICTION_BLOCK}

   auth_basic "Admin Access Required";
   auth_basic_user_file /etc/nginx/htpasswd/.htpasswd;
   ```
2. Insert OAuth2-Proxy auth handling:
   ```nginx
   auth_request /oauth2/auth;
   error_page 401 = @oauth_error;
   error_page 403 = @oauth_error;

   auth_request_set $user $upstream_http_x_auth_request_user;
   auth_request_set $email $upstream_http_x_auth_request_email;
   proxy_set_header X-Forwarded-User $user;
   proxy_set_header X-Forwarded-Email $email;
   ```
3. At the end of the `server {}` block, add:
   ```nginx
   location /oauth2/ {
       proxy_pass http://oauth2_proxy:4180;
       proxy_set_header Host $host;
       proxy_set_header X-Real-IP $remote_addr;
       proxy_set_header X-Scheme $scheme;
       proxy_set_header X-Auth-Request-Redirect $request_uri;
   }

   # Allow sign-out
   location /oauth2/sign_out {
       proxy_pass http://oauth2_proxy:4180;
       proxy_set_header Host $host;
   }

   # Unified error redirect
   location @oauth_error {
       return 302 /oauth2/start?rd=$scheme://$host$request_uri;
   }
   ```
4. If `nginx/nginx.prod.conf.template` includes `cloudflare_ips.conf`, remove that line or supply a static file to avoid startup failures.
5. In `nginx/nginx.prod.conf.template`, define an upstream for the proxy:
   ```nginx
   upstream oauth2_proxy {
       server oauth2_proxy:4180;
       keepalive 2;
   }
   ```

## 5. Simplify `nginx/entrypoint.sh`
Replace the script with a minimal template renderer:

```bash
#!/bin/sh
set -e

TEMPLATE_DIR="/etc/nginx/templates"
CONFIG_DIR="/etc/nginx/conf.d"

mkdir -p ${CONFIG_DIR}

if [ ! -d "${TEMPLATE_DIR}" ]; then
  echo "Template directory ${TEMPLATE_DIR} not found."
  exit 1
fi

echo "Rendering Nginx config files from environment variables..."
for template in $(find "${TEMPLATE_DIR}" -maxdepth 1 -type f -name "*.template"); do
  output_file="${CONFIG_DIR}/$(basename "${template}" .template)"
  envsubst < "${template}" > "${output_file}"
  echo "Generated: ${output_file}"
 done

envsubst < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf

echo "Configuration rendering complete."
exec "$@"
```

## 6. Remove Legacy Files
Clean up assets no longer required:
- Delete the `nginx/htpasswd` directory.
- Remove any references to `cloudflare_ips.conf` unless a static file is provided.

## 7. Apply Changes and Restart Services
1. Shut down running services:
   ```bash
   docker-compose -f docker-compose.prod.yml down
   ```
2. Rebuild and start:
   ```bash
   docker-compose -f docker-compose.prod.yml up --build -d
   ```

## 8. Verify Migration
Ensure the new authentication flow works and services are healthy:
```bash
# Check oauth2_proxy logs
docker-compose -f docker-compose.prod.yml logs oauth2_proxy

# Test redirect behavior
curl -I https://pgadmin.your-domain.com/

# Hit auth endpoint directly
curl -I https://pgadmin.your-domain.com/oauth2/auth

# Inspect container states
docker-compose -f docker-compose.prod.yml ps
```

## 9. Rollback Plan
If issues arise, revert to the previous setup:
```bash
cp .env.prod.backup .env.prod
git checkout HEAD~1 -- docker-compose.prod.yml nginx/
docker-compose -f docker-compose.prod.yml up -d --force-recreate
```

## 10. Enable Multi-Factor Authentication
Since access now relies on GitHub credentials, enable MFA on your GitHub account for improved security.

---
Follow these steps to fully migrate your admin dashboards to OAuth2-Proxy with a cleaner and more flexible authentication setup.
