# Analytics Dashboard JWT Authentication Setup

## Overview
The Analytics Dashboard is now protected with JWT authentication, using the same auth system as the HazeBot Admin app. This provides:
- Secure access control (admin/mod roles only)
- Bitwarden password manager support
- Token-based authentication (no cookies)
- Seamless integration with existing HazeBot auth

## Architecture

```
User Request → NGINX (your-domain.com:443)
              ↓
              auth_request → Flask Backend (/api/auth/verify-token)
              ↓                ↓
          JWT Valid?       401/403 Error
              ↓
          Proxy → Analytics Server (localhost:8089)
```

## Components

### 1. NGINX Configuration (`nginx_analytics_jwt.conf`)
- Intercepts `/analytics/` requests
- Calls Flask JWT verification endpoint via `auth_request`
- Proxies to Analytics server if JWT is valid
- Returns 401 error if authentication fails

### 2. Flask JWT Verification Endpoint (`/api/auth/verify-token`)
- Added to `api/auth_routes.py`
- Validates JWT token structure and signature
- Checks token expiry
- Verifies user has admin/mod permissions
- Returns HTTP 200 (valid) or 401/403 (invalid/forbidden)

### 3. Analytics Server (`analytics/view_analytics.py`)
- Already configured with redirect logic (`/analytics` → `/analytics/`)
- Serves dashboard at `/analytics/analytics_dashboard.html`
- No changes needed - authentication handled by NGINX

## Deployment Steps

### Step 1: Update NGINX Configuration

1. SSH into production server:
   ```bash
   ssh root@YOUR_SERVER
   ```

2. Edit the NGINX config for your domain:
   ```bash
   nano /etc/nginx/sites-available/your-domain
   ```

3. Add the contents of `nginx_analytics_jwt.conf` inside the `server` block (after existing location blocks).

4. Test NGINX config:
   ```bash
   nginx -t
   ```

5. Reload NGINX:
   ```bash
   systemctl reload nginx
   ```

### Step 2: Deploy Flask Backend Changes

1. On production server, pull latest code:
   ```bash
   cd /path/to/HazeBot
   git pull origin main
   ```

2. Restart Flask backend (if running in Docker):
   ```bash
   docker restart <backend-container-name>
   ```

   Or if running with systemd:
   ```bash
   systemctl restart hazebot-api
   ```

### Step 3: Ensure Analytics Server is Running

1. Check if Analytics server is running:
   ```bash
   ps aux | grep view_analytics.py
   ```

2. If not running, start it:
   ```bash
   cd /path/to/HazeBot/analytics
   python3 view_analytics.py &
   ```

3. Or create a systemd service for it (recommended).

## Testing

### Test 1: Verify NGINX Config
```bash
curl -I https://your-domain.com/analytics/
```
Expected: `401` (Unauthorized)

### Test 2: Get JWT Token
```bash
curl -X POST https://your-domain.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"your-username","password":"your-password"}'
```
Expected: `{"token":"eyJ...", "user":"...", "role":"admin", ...}`

### Test 3: Access Analytics with Token
```bash
TOKEN="<token-from-step-2>"
curl -I https://your-domain.com/analytics/ \
  -H "Authorization: Bearer $TOKEN"
```
Expected: `200 OK` (then redirects to `/analytics/analytics_dashboard.html`)

### Test 4: Browser Access

1. Open browser developer tools (F12)
2. Go to Console tab
3. Execute:
   ```javascript
   // Get token (replace with actual username/password)
   fetch('https://your-domain.com/api/auth/login', {
     method: 'POST',
     headers: { 'Content-Type': 'application/json' },
     body: JSON.stringify({ username: 'your-username', password: 'your-password' })
   })
   .then(r => r.json())
   .then(data => {
     localStorage.setItem('jwt_token', data.token);
     console.log('Token saved:', data.token);
   });
   ```

4. Install a browser extension to add Authorization headers (e.g., "ModHeader")
5. Add header: `Authorization: Bearer <token>`
6. Navigate to `https://your-domain.com/analytics/`

### Test 5: Bitwarden Integration

1. In Bitwarden, create a new Login item:
   - Name: "HazeBot Analytics"
   - Username: `<your-username>`
   - Password: `<your-password>`
   - URI: `https://your-domain.com/analytics`

2. Create a login page (optional) or use the API directly with a tool that supports Bitwarden.

## Security Notes

### Token Format
- Algorithm: HS256 (HMAC-SHA256)
- Secret Key: `SECRET_KEY` from Flask app config (set in .env)
- Expiry: 7 days (for legacy auth), varies for Discord OAuth

### Token Payload Example
```json
{
  "user": "admin",
  "discord_id": "legacy_user",
  "exp": 1234567890,
  "role": "admin",
  "permissions": ["all"],
  "auth_type": "legacy",
  "session_id": "abc123..."
}
```

### Permissions
Only users with `admin` or `mod` role can access Analytics.
Lootlings (regular Discord members) are denied with 403 Forbidden.

### Token Storage
- **HazeBot Admin App**: Stored in Flutter secure storage
- **Browser Access**: Store in `localStorage` or use an extension
- **Bitwarden**: Use username/password, get token via `/api/auth/login`

## Troubleshooting

### Issue: 401 Unauthorized
- Check if token is expired (7 days for legacy auth)
- Verify token format: `Authorization: Bearer <token>`
- Check Flask logs for JWT decode errors

### Issue: 403 Forbidden
- User doesn't have admin/mod role
- Check Discord roles (ADMIN_ROLE_ID, MODERATOR_ROLE_ID in .env)

### Issue: NGINX 502 Bad Gateway
- Analytics server (8089) not running
- Flask backend not responding
- Check Docker container status

### Issue: Token Verification Takes Too Long
- NGINX auth_request timeout (default 60s)
- Increase timeout in NGINX config:
  ```nginx
  proxy_read_timeout 90s;
  proxy_connect_timeout 90s;
  ```

## Environment Variables

Required in `.env` file:
- `SECRET_KEY`: Flask JWT signing key
- `API_ADMIN_USER`: Admin username
- `API_ADMIN_PASS`: Admin password
- `API_EXTRA_USERS`: Additional users (format: `user1:pass1,user2:pass2`)
- `DISCORD_CLIENT_ID`: Discord OAuth2 client ID (for Discord login)
- `DISCORD_CLIENT_SECRET`: Discord OAuth2 client secret

## Alternative: Discord OAuth2 Login

If you want to use Discord login instead of username/password:

1. Initiate OAuth2 flow:
   ```bash
   curl https://your-domain.com/api/discord/auth
   ```

2. Visit the returned `auth_url` in browser
3. Authorize the app
4. Get JWT token from callback

This requires Discord app setup (see `FIREBASE_SETUP.md` for details).

## Files Modified

- `api/auth_routes.py`: Added `/api/auth/verify-token` endpoint
- `analytics/nginx_analytics_jwt.conf`: NGINX config for JWT auth
- `analytics/ANALYTICS_JWT_SETUP.md`: This documentation

## Next Steps

1. Deploy NGINX config to production
2. Test JWT authentication
3. Create a login page (optional, for browser access)
4. Update Analytics dashboard UI to show logged-in user
5. Add logout functionality
6. Consider implementing token refresh mechanism

## 📚 Related Documentation

- **Analytics Overview**: `README.md` - Complete analytics system documentation
- **Deployment Summary**: `DEPLOYMENT_SUMMARY.md` - Quick deployment reference
- **API Documentation**: `../api/README.md` - REST API endpoints and authentication
- **Main README**: `../README.md` - HazeBot overview and setup
