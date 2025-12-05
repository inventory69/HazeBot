# HazeBot API

Comprehensive REST API and WebSocket server for the HazeBot Discord bot ecosystem, providing configuration management, ticket system, analytics, and real-time notifications.

## Features

### Authentication & Security
- **JWT-based Authentication** - Secure token-based auth with role-based access control
- **Discord OAuth2** - Seamless Discord login integration
- **Multi-user Support** - Admin, moderator, and user roles with different permissions
- **Session Management** - Persistent sessions with automatic cleanup

### Core Systems
- **Ticket System** - Full-featured support ticket management with real-time chat
- **Analytics** - Comprehensive usage tracking with SQLite database
- **Configuration Management** - Complete bot configuration via REST API
- **Notification System** - Real-time notifications with Firebase Cloud Messaging (FCM)
- **WebSocket Server** - Real-time updates for tickets and chat messages
- **Rocket League Integration** - Player stats tracking and rank monitoring
- **Meme System** - Reddit and Lemmy integration with template support
- **Cog Management** - Dynamic loading/unloading of Discord bot modules

### Technical Features
- **CORS Enabled** - Full support for web and mobile Flutter apps
- **Platform-Aware** - Different URLs for Web, Android, iOS
- **Caching** - Redis-like caching for performance optimization
- **Error Tracking** - Comprehensive logging and error handling
- **Rate Limiting** - Protection against API abuse
- **Database** - SQLite for analytics, JSON for configuration

## Installation

```bash
pip install -r api_requirements.txt
```

## Environment Variables

Add these to your `.env` file:

```env
# API Configuration
API_PORT=5070
SECRET_KEY=your-secret-key-here
API_ADMIN_USER=admin
API_ADMIN_PASS=your-secure-password
API_EXTRA_USERS=user1:pass1,user2:pass2

# Discord Configuration
DISCORD_TOKEN=your-bot-token
DISCORD_CLIENT_ID=your-client-id
DISCORD_CLIENT_SECRET=your-client-secret
DISCORD_REDIRECT_URI=https://your-domain.com/api/discord/callback

# Discord Role IDs
ADMIN_ROLE_ID=123456789
MODERATOR_ROLE_ID=987654321
LOOTLING_ROLE_ID=111222333

# Firebase Cloud Messaging (FCM)
FCM_SERVER_KEY=your-fcm-server-key

# Rocket League API
ROCKET_LEAGUE_API_KEY=your-rl-api-key

# Redis (optional, for caching)
REDIS_HOST=localhost
REDIS_PORT=6379

# CORS Origins
CORS_ORIGINS=https://your-domain.com,http://localhost:3000
```

## Running the API

### Development
```bash
cd api
python app.py
```

### Production (Docker)
```bash
docker-compose up -d
```

### Production (Systemd)
```bash
systemctl start hazebot-api
```

The API will be available at:
- **Local**: `http://localhost:5070`
- **Production**: `https://your-domain.com` (via NGINX reverse proxy)

## API Endpoints

All endpoints (except health check and login) require authentication. Include the JWT token in the Authorization header:
```
Authorization: Bearer <token>
```

### 🔐 Authentication (`auth_routes.py`)

#### POST `/api/auth/login`
Login with username/password and receive JWT token.

**Request:**
```json
{
  "username": "admin",
  "password": "your-password"
}
```

**Response:**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": "admin",
  "role": "admin",
  "discord_id": "legacy_user",
  "permissions": ["all"]
}
```

#### POST `/api/auth/verify-token`
Verify JWT token validity (used by NGINX auth_request).

**Headers:**
```
Authorization: Bearer <token>
```

**Response:** `200 OK` or `401 Unauthorized`

#### GET `/api/discord/auth`
Initiate Discord OAuth2 flow.

**Response:**
```json
{
  "auth_url": "https://discord.com/api/oauth2/authorize?..."
}
```

#### GET `/api/discord/callback`
Discord OAuth2 callback (handles redirect after authorization).

**Query Params:** `code`, `state`, `platform` (web/android/ios)

**Response:** Redirects to app with token

### 🎫 Ticket System (`ticket_routes.py`)

#### GET `/api/tickets`
Get all tickets (admin/mod: all tickets, user: own tickets).

**Query Params:** `status` (open/closed/all)

**Response:**
```json
{
  "tickets": [
    {
      "ticket_id": "1234567890",
      "user_id": "987654321",
      "user_name": "Username",
      "status": "open",
      "created_at": "2024-12-05T10:30:00Z",
      "last_message": "Latest message text",
      "unread_count": 2
    }
  ]
}
```

#### GET `/api/tickets/<ticket_id>`
Get specific ticket details.

**Response:**
```json
{
  "ticket_id": "1234567890",
  "user_id": "987654321",
  "user_name": "Username",
  "user_avatar": "https://cdn.discordapp.com/avatars/...",
  "status": "open",
  "created_at": "2024-12-05T10:30:00Z",
  "messages": [
    {
      "id": "msg_123",
      "author_id": "987654321",
      "author_name": "Username",
      "author_avatar": "https://...",
      "content": "Message text",
      "timestamp": "2024-12-05T10:31:00Z",
      "is_admin": false
    }
  ]
}
```

#### POST `/api/tickets/<ticket_id>/send`
Send message in ticket.

**Request:**
```json
{
  "message": "Your message text"
}
```

**Response:**
```json
{
  "success": true,
  "message": {
    "id": "msg_456",
    "author_id": "987654321",
    "content": "Your message text",
    "timestamp": "2024-12-05T10:32:00Z"
  }
}
```

#### POST `/api/tickets/<ticket_id>/close`
Close ticket (admin/mod only).

**Response:**
```json
{
  "success": true,
  "message": "Ticket closed"
}
```

#### POST `/api/tickets/<ticket_id>/reopen`
Reopen closed ticket.

**Response:**
```json
{
  "success": true,
  "message": "Ticket reopened"
}
```

#### DELETE `/api/tickets/<ticket_id>`
Delete ticket (admin only).

**Response:**
```json
{
  "success": true,
  "message": "Ticket deleted"
}
```

#### POST `/api/tickets/<ticket_id>/mark-read`
Mark ticket as read (clear unread count).

**Response:**
```json
{
  "success": true
}
```

### 🔔 Notifications (`notification_routes.py`)

#### POST `/api/notifications/register-token`
Register FCM device token for push notifications.

**Request:**
```json
{
  "fcm_token": "your-fcm-device-token",
  "platform": "android"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Token registered"
}
```

#### POST `/api/notifications/test`
Send test notification (admin only).

**Request:**
```json
{
  "fcm_token": "device-token",
  "title": "Test",
  "body": "Test notification"
}
```

#### WebSocket Events (SocketIO)

**Connect:** `io.connect('wss://your-domain.com', { auth: { token: 'jwt-token' } })`

**Events:**
- `join_ticket` - Join ticket room for real-time updates
  ```javascript
  socket.emit('join_ticket', { ticket_id: '1234567890' });
  ```

- `leave_ticket` - Leave ticket room
  ```javascript
  socket.emit('leave_ticket', { ticket_id: '1234567890' });
  ```

- `new_message` - Receive new message in ticket
  ```javascript
  socket.on('new_message', (data) => {
    // data.ticket_id, data.message, data.messageData
  });
  ```

- `message_history` - Receive message history after joining
  ```javascript
  socket.on('message_history', (data) => {
    // data.ticket_id, data.messages
  });
  ```

### 📊 Analytics (`view_analytics.py`, `analytics/*.py`)

See `analytics/README.md` for complete analytics documentation.

#### GET `/api/stats`
Get analytics overview (admin only).

**Query Params:** `days` (7/30/90 or omit for all-time)

**Response:**
```json
{
  "total_users": 150,
  "active_users_7d": 45,
  "total_sessions": 1234,
  "avg_session_duration": 180,
  "total_actions": 5678
}
```

#### GET `/api/active-sessions`
Get currently active sessions (admin only).

**Response:**
```json
{
  "sessions": [
    {
      "session_id": "sess_123",
      "user_id": "987654321",
      "platform": "android",
      "last_activity": "2024-12-05T10:35:00Z",
      "duration": 300
    }
  ]
}
```

### ⚙️ Configuration (`config_routes.py`)

#### GET `/api/config`
Get all bot configuration (admin only).

**Response:**
```json
{
  "general": { "bot_name": "HazeBot", "command_prefix": "!" },
  "channels": { "log_channel_id": "123456789" },
  "roles": { "admin_role_id": "987654321" },
  "meme": { "default_subreddits": ["memes", "dankmemes"] },
  "rocket_league": { "rank_check_interval_hours": 24 },
  "welcome": { "welcome_messages": ["Welcome!"] },
  "server_guide": { "categories": [] }
}
```

#### GET/PUT `/api/config/general`
Get or update general bot settings.

**Fields:** `bot_name`, `command_prefix`, `presence_update_interval`, `message_cooldown`, `fuzzy_matching_threshold`

#### GET/PUT `/api/config/channels`
Get or update channel IDs.

**Fields:** `log_channel_id`, `changelog_channel_id`, `todo_channel_id`, `rl_channel_id`, `meme_channel_id`, `server_guide_channel_id`, `welcome_rules_channel_id`, `welcome_public_channel_id`, `transcript_channel_id`, `tickets_category_id`

#### GET/PUT `/api/config/roles`
Get or update role IDs.

**Fields:** `admin_role_id`, `moderator_role_id`, `normal_role_id`, `member_role_id`, `changelog_role_id`, `meme_role_id`, `interest_role_ids`, `interest_roles`

#### GET/PUT `/api/config/meme`
Get or update meme system configuration.

**Fields:** `default_subreddits`, `default_lemmy`, `meme_sources`, `templates_cache_duration`

#### GET/PUT `/api/config/rocket_league`
Get or update Rocket League configuration.

**Fields:** `rank_check_interval_hours`, `rank_cache_ttl_seconds`

#### GET/PUT `/api/config/welcome`
Get or update welcome system configuration.

**Fields:** `rules_text`, `welcome_messages`

#### GET/PUT `/api/config/server_guide`
Get or update server guide configuration.

#### GET/PUT `/api/config/tickets`
Get or update ticket system configuration (admin only).

**Fields:** `enabled`, `max_open_per_user`, `auto_close_hours`, `transcript_enabled`

### 🎮 Rocket League (`rocket_league_routes.py`)

#### GET `/api/rocket-league/stats/<platform>/<username>`
Get Rocket League player stats.

**Platforms:** `steam`, `epic`, `psn`, `xbl`

**Response:**
```json
{
  "username": "PlayerName",
  "platform": "steam",
  "ranks": {
    "1v1": { "tier": "Diamond I", "division": 3, "mmr": 950 },
    "2v2": { "tier": "Champion II", "division": 2, "mmr": 1150 }
  },
  "cached": false
}
```

#### POST `/api/rocket-league/check-ranks`
Manually trigger rank check for all tracked players (admin only).

### 🎭 Cog Management (`cog_routes.py`)

#### GET `/api/cogs`
List all available cogs (admin only).

**Response:**
```json
{
  "cogs": [
    { "name": "General", "loaded": true },
    { "name": "Moderation", "loaded": false }
  ]
}
```

#### POST `/api/cogs/load`
Load a cog (admin only).

**Request:**
```json
{
  "cog_name": "Moderation"
}
```

#### POST `/api/cogs/unload`
Unload a cog (admin only).

#### POST `/api/cogs/reload`
Reload a cog (admin only).

### 🧑‍💼 User Management (`user_routes.py`)

#### GET `/api/users/me`
Get current user info.

**Response:**
```json
{
  "user_id": "987654321",
  "username": "Username",
  "discriminator": "1234",
  "avatar": "https://cdn.discordapp.com/avatars/...",
  "role": "admin",
  "permissions": ["all"]
}
```

#### GET `/api/users/<user_id>`
Get specific user info (admin only).

### 👮 Admin (`admin_routes.py`)

#### GET `/api/admin/stats`
Get system statistics (admin only).

**Response:**
```json
{
  "bot_uptime": 86400,
  "total_guilds": 1,
  "total_members": 150,
  "total_tickets": 45,
  "open_tickets": 12
}
```

#### POST `/api/admin/broadcast`
Send broadcast message to all users (admin only).

**Request:**
```json
{
  "title": "Announcement",
  "message": "Important update",
  "priority": "high"
}
```

### 🎨 Meme System (`meme_routes.py`)

#### GET `/api/memes/random`
Get random meme from configured sources.

**Query Params:** `source` (reddit/lemmy)

**Response:**
```json
{
  "title": "Funny meme",
  "url": "https://i.redd.it/...",
  "source": "reddit",
  "subreddit": "memes"
}
```

### 🏥 Health Check

#### GET `/api/health`
Health check endpoint (no auth required).

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2024-12-05T10:40:00Z"
}
```

## Example Usage

### Python
```python
import requests

# Login
response = requests.post('https://your-domain.com/api/auth/login', json={
    'username': 'admin',
    'password': 'your-password'
})
data = response.json()
token = data['token']

# Get tickets
headers = {'Authorization': f'Bearer {token}'}
tickets = requests.get('https://your-domain.com/api/tickets', headers=headers).json()

# Send message in ticket
requests.post('https://your-domain.com/api/tickets/1234567890/send',
    headers=headers,
    json={'message': 'Hello from API'}
)

# Get analytics
stats = requests.get('https://your-domain.com/api/stats?days=7', headers=headers).json()
print(f"Active users (7d): {stats['active_users_7d']}")
```

### JavaScript (WebSocket)
```javascript
import io from 'socket.io-client';

// Connect with JWT token
const socket = io('wss://your-domain.com', {
  auth: { token: 'your-jwt-token' }
});

// Join ticket room
socket.emit('join_ticket', { ticket_id: '1234567890' });

// Listen for new messages
socket.on('new_message', (data) => {
  console.log('New message:', data.messageData);
});

// Disconnect
socket.on('disconnect', () => {
  console.log('Disconnected from server');
});
```

### Flutter (Dart)
```dart
import 'package:http/http.dart' as http;
import 'dart:convert';

// Login
final loginResponse = await http.post(
  Uri.parse('https://your-domain.com/api/auth/login'),
  headers: {'Content-Type': 'application/json'},
  body: jsonEncode({'username': 'admin', 'password': 'password'}),
);
final token = jsonDecode(loginResponse.body)['token'];

// Get tickets
final ticketsResponse = await http.get(
  Uri.parse('https://your-domain.com/api/tickets'),
  headers: {'Authorization': 'Bearer $token'},
);
final tickets = jsonDecode(ticketsResponse.body)['tickets'];
```

## Architecture

### File Structure
```
api/
├── app.py                      # Main Flask application
├── auth_routes.py              # Authentication (JWT, Discord OAuth)
├── ticket_routes.py            # Ticket system endpoints
├── notification_routes.py      # FCM notifications + WebSocket
├── analytics.py                # Analytics tracking
├── analytics_db.py             # SQLite database operations
├── analytics_partitioning.py   # Database partitioning
├── feature_analytics.py        # Feature usage tracking
├── config_routes.py            # Bot configuration endpoints
├── rocket_league_routes.py     # Rocket League integration
├── cog_routes.py               # Discord cog management
├── user_routes.py              # User management
├── admin_routes.py             # Admin operations
├── meme_routes.py              # Meme system
├── cache.py                    # Caching utilities
├── helpers.py                  # Utility functions
├── error_tracking.py           # Error logging
└── routes/                     # Additional route modules
```

### Tech Stack
- **Flask** - Web framework
- **Flask-SocketIO** - WebSocket support
- **Flask-CORS** - Cross-origin resource sharing
- **PyJWT** - JWT token handling
- **SQLite** - Analytics database
- **discord.py** - Discord bot integration
- **Firebase Admin SDK** - Push notifications
- **Redis** (optional) - Caching layer

### Deployment
- **NGINX** - Reverse proxy with SSL/TLS
- **Docker** - Containerized deployment
- **Systemd** - Service management
- **Let's Encrypt** - SSL certificates

## Security Notes

### Production Checklist
- ✅ Change default credentials (`API_ADMIN_USER`, `API_ADMIN_PASS`)
- ✅ Use strong `SECRET_KEY` (32+ characters, random)
- ✅ Enable HTTPS only (disable HTTP in production)
- ✅ Configure CORS origins restrictively
- ✅ Implement rate limiting (use NGINX or Flask-Limiter)
- ✅ Keep JWT tokens short-lived (7 days max)
- ✅ Rotate `FCM_SERVER_KEY` periodically
- ✅ Use environment variables (never commit `.env`)
- ✅ Enable firewall rules (allow only necessary ports)
- ✅ Monitor logs for suspicious activity
- ✅ Keep dependencies updated (`pip list --outdated`)

### Authentication Flow
1. User logs in (username/password or Discord OAuth)
2. Server validates credentials and Discord roles
3. Server issues JWT token (includes user_id, role, permissions)
4. Client stores token (secure storage on mobile, localStorage on web)
5. Client includes token in `Authorization: Bearer <token>` header
6. Server validates token on each request
7. Token expires after 7 days (user must re-login)

### Role-Based Access Control (RBAC)
- **Admin** - Full access (all endpoints, all operations)
- **Moderator** - Ticket management, user management, analytics (read-only)
- **Lootling** - Own tickets only, limited endpoints

### WebSocket Security
- JWT token required for connection (passed in `auth` object)
- Room-based access control (users can only join their own ticket rooms)
- Rate limiting on message sending (prevent spam)
- Automatic disconnect on token expiry

## Troubleshooting

### Common Issues

**Issue:** `401 Unauthorized` on all requests
- **Solution:** Check if token is valid and not expired. Re-login to get new token.

**Issue:** WebSocket connection fails
- **Solution:** Ensure token is passed in `auth` object during connection. Check NGINX WebSocket configuration.

**Issue:** `CORS error` in web browser
- **Solution:** Add your domain to `CORS_ORIGINS` in `.env`. Restart API server.

**Issue:** Analytics not updating
- **Solution:** Check if `analytics_db.py` can write to database. Verify file permissions on `Data/app_analytics.db`.

**Issue:** Push notifications not working
- **Solution:** Verify `FCM_SERVER_KEY` is correct. Check device token registration.

**Issue:** Discord OAuth fails
- **Solution:** Verify `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, and `DISCORD_REDIRECT_URI` match Discord Developer Portal settings.

### Logs
- **Flask logs:** `Logs/hazebot-api.log`
- **Analytics logs:** `Logs/analytics.log`
- **Error logs:** `Logs/error.log`
- **NGINX logs:** `/var/log/nginx/error.log`, `/var/log/nginx/access.log`

### Debugging
```bash
# Enable Flask debug mode (development only!)
export FLASK_ENV=development
export FLASK_DEBUG=1
python app.py

# Check database
sqlite3 Data/app_analytics.db "SELECT COUNT(*) FROM sessions;"

# Test token validity
curl -H "Authorization: Bearer <token>" https://your-domain.com/api/auth/verify-token

# Monitor WebSocket connections
tail -f Logs/hazebot-api.log | grep -i websocket
```

## 📚 Documentation

### API-Specific
- **API Refactoring**: `API_REFACTORING.md` - Code organization and blueprint architecture

### Analytics System
- **Analytics Overview**: `../analytics/README.md` - Complete analytics documentation
- **JWT Setup**: `../analytics/ANALYTICS_JWT_SETUP.md` - JWT authentication guide
- **Deployment**: `../analytics/DEPLOYMENT_SUMMARY.md` - Deployment checklist

### General Documentation
- **Main README**: `../README.md` - HazeBot overview and feature list
- **Bot Setup**: `../docs/BOT_SETUP.md` - Discord bot installation guide
- **Architecture**: `../docs/ARCHITECTURE.md` - System architecture documentation
- **Contributing**: `../docs/CONTRIBUTING.md` - Development guidelines

## Contributing

1. Create feature branch: `git checkout -b feature/my-feature`
2. Make changes and test thoroughly
3. Update documentation (README, inline comments)
4. Commit with descriptive message: `git commit -m "feat: add X endpoint"`
5. Push and create pull request

## License

See `../LICENSE` for license information.
