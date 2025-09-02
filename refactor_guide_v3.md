# Centralized OAuth2 Login Refactor Guide (v3)

This guide walks through consolidating all admin dashboard logins under a single subdomain `auth.your-domain.com`. The centralized flow lets every subdomain share one OAuth callback URL and cookie domain.

## 1. Register or Update the GitHub OAuth App
1. Navigate to **Settings → Developer settings → OAuth Apps** in GitHub.
2. Create or update an app with:
   - **Homepage URL**: `https://your-domain.com`
   - **Authorization callback URL**: `https://auth.your-domain.com/oauth2/callback`
3. Save the **Client ID** and **Client Secret** for `.env.prod`.

## 2. Configure `.env.prod`
Append OAuth2-Proxy variables or update existing ones:

```bash
OAUTH2_PROXY_REDIRECT_URL="https://auth.your-domain.com/oauth2/callback"
OAUTH2_PROXY_CLIENT_ID="YOUR_GITHUB_CLIENT_ID"
OAUTH2_PROXY_CLIENT_SECRET="YOUR_GITHUB_CLIENT_SECRET"
OAUTH2_PROXY_PROVIDER="github"
OAUTH2_PROXY_COOKIE_SECRET="PASTE_RANDOM_STRING"
OAUTH2_PROXY_COOKIE_DOMAINS=".your-domain.com"
OAUTH2_PROXY_COOKIE_SECURE="true"
OAUTH2_PROXY_EMAIL_DOMAINS="*"      # tighten to your org if needed
OAUTH2_PROXY_SET_XAUTHREQUEST="true"
OAUTH2_PROXY_PASS_ACCESS_TOKEN="true"
OAUTH2_PROXY_UPSTREAMS="file:///dev/null"
```

## 3. Expose `auth.your-domain.com` via Nginx
1. Create `nginx/conf/prod/auth.conf.template`:
   ```nginx
   # OAuth2 login endpoint
   server {
       listen 443 ssl http2;
       server_name auth.${DOMAIN_MAIN};

       ssl_certificate /etc/nginx/ssl/server.pem;
       ssl_certificate_key /etc/nginx/ssl/server.key;

       location / {
           proxy_pass http://oauth2_proxy;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Scheme $scheme;
       }
   }
   ```
2. Reference this template from `nginx/nginx.prod.conf.template` if needed using `include /etc/nginx/conf.d/auth.conf;`.

## 4. Update Service Templates
For each of:
- `nginx/conf/prod/portainer.conf.template`
- `nginx/conf/prod/pgadmin.conf.template`
- `nginx/conf/prod/redisinsight.conf.template`

apply the following changes:

1. **Proxy all OAuth locations to the auth domain**
   ```nginx
   location /oauth2/ {
       proxy_pass https://auth.${DOMAIN_MAIN}/oauth2/;
       proxy_set_header Host auth.${DOMAIN_MAIN};
       proxy_set_header X-Real-IP $remote_addr;
       proxy_set_header X-Scheme $scheme;
   }
   ```
2. **Redirect errors to the central login**
   ```nginx
   location @oauth_error {
       return 302 https://auth.${DOMAIN_MAIN}/oauth2/start?rd=$scheme://$host$request_uri;
   }
   ```
3. Optionally forward sign-out requests:
   ```nginx
   location /oauth2/sign_out {
       proxy_pass https://auth.${DOMAIN_MAIN}/oauth2/sign_out;
       proxy_set_header Host auth.${DOMAIN_MAIN};
   }
   ```
4. Keep the existing `auth_request` blocks so each subdomain still verifies sessions:
   ```nginx
   auth_request /oauth2/auth;
   error_page 401 = @oauth_error;
   error_page 403 = @oauth_error;

   auth_request_set $user $upstream_http_x_auth_request_user;
   auth_request_set $email $upstream_http_x_auth_request_email;
   proxy_set_header X-Forwarded-User $user;
   proxy_set_header X-Forwarded-Email $email;
   ```

## 5. Rebuild and Restart
```bash
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up --build -d
```

## 6. Verify Centralized Login
```bash
# Test redirect
curl -I https://portainer.your-domain.com/

# Trigger auth check via central domain
curl -I https://auth.your-domain.com/oauth2/auth

# Inspect container logs
docker compose -f docker-compose.prod.yml logs oauth2_proxy
```

With these changes, all admin subdomains share a single OAuth2 login hosted at `auth.your-domain.com`, reducing the number of callback URLs required by the provider.
