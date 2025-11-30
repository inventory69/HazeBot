# HazeBot Architecture 🏗️

This document describes the technical architecture of HazeBot.

## Modular Blueprint API (Version 3.8)

The Flask API was refactored from a monolithic 6500-line file into a clean, modular Blueprint-based architecture:

### Main Application
- **`api/app.py`** (301 lines) - Flask setup, middleware, Blueprint registration

### Blueprint Modules
Organized by feature area:

- `auth_routes.py` - Authentication & sessions
- `admin_routes.py` - Admin monitoring & logs
- `config_routes.py` - Bot configuration
- `meme_routes.py` - Meme generation & daily memes
- `rocket_league_routes.py` - RL stats integration
- `ticket_routes.py` - Support ticket system
- `hazehub_cogs_routes.py` - Dashboard features
- `cog_routes.py` - Cog management
- `user_routes.py` - User profiles
- `notification_routes.py` - Push & WebSocket

### Benefits
- ✅ **Maintainability** - Clear separation of concerns
- ✅ **Testability** - Easier to test individual modules
- ✅ **Scalability** - Add features as new Blueprints
- ✅ **Performance** - Smart caching with TTL

---

## Cog System

HazeBot uses discord.py's Cog system for modularity:

### Key Features
- **Hot-reload support** - Reload cogs without restart
- **APIServer as Cog** - Manage via `/api/cogs` endpoints
- **Protection** - Critical cogs (CogManager) cannot be unloaded

### Available Cogs (22 total)
- **APIServer.py** - API as loadable Cog
- **CogManager.py** - Cog management
- **RocketLeague.py** - RL integration
- **DailyMeme.py** - Meme system
- **TicketSystem.py** - Support tickets
- **Moderation.py** - Mod tools
- **Welcome.py** - Onboarding system
- **Changelog.py** - Version management
- **TodoList.py** - Task management
- **Warframe.py** - Warframe integration
- And 12 more...

---

## Project Structure

```
HazeBot/
├── Main.py                    # Bot entry point (standalone)
├── start_with_api.py          # Bot + API Server (Port 5070)
├── Config.py                  # Bot configuration (not in git)
│
├── Cogs/                      # Modular bot features (22 cogs)
│   ├── APIServer.py          # API as loadable Cog
│   ├── CogManager.py         # Cog management
│   ├── RocketLeague.py       # RL integration
│   ├── DailyMeme.py          # Meme system
│   ├── TicketSystem.py       # Support tickets
│   ├── Moderation.py         # Mod tools
│   ├── Welcome.py            # Onboarding
│   ├── Changelog.py          # Version management
│   ├── TodoList.py           # Task management
│   ├── Warframe.py           # Warframe integration
│   └── ...                   # 12 more cogs
│
├── api/                       # REST API (Blueprint architecture)
│   ├── app.py                # Main Flask app (301 lines)
│   ├── helpers.py            # Helper functions
│   ├── auth.py               # JWT middleware
│   ├── cache.py              # Caching system
│   └── *_routes.py           # Blueprint modules (10 files)
│
├── Utils/                     # Shared utilities
│   ├── Logger.py             # Rich logging with colors
│   ├── CacheUtils.py         # Caching system
│   ├── ConfigLoader.py       # Config management
│   └── DatabaseManager.py    # Database utilities
│
├── Data/                      # SQLite databases
│   ├── memes.db              # Meme tracking
│   ├── tickets.db            # Support tickets
│   ├── users.db              # User profiles
│   └── warnings.db           # Moderation warnings
│
├── Cache/                     # API response cache
│   ├── rl_stats:*.json       # Rocket League stats
│   ├── warframe_*.json       # Warframe data
│   └── ...                   # Other cached data
│
├── Logs/                      # Log files
│   ├── bot.log               # Main bot logs
│   ├── api.log               # API logs
│   └── error.log             # Error logs
│
└── .env                       # Environment variables (not in git)
```

---

## Technology Stack

### Backend
- **Python 3.11+** - Modern Python features
- **discord.py 2.0+** - Discord API wrapper
- **Flask 3.0+** - Web framework for API
- **SQLite** - Lightweight database

### API Layer
- **JWT Authentication** - Secure token-based auth
- **Blueprint Architecture** - Modular routing
- **Smart Caching** - TTL-based response caching
- **CORS Support** - Cross-origin requests

### Frontend
- **Flutter 3.0+** - Cross-platform UI framework
- **Material Design 3** - Modern design system
- **Riverpod** - State management

---

## Data Flow

### Bot Commands
```
Discord User → Bot Command → Cog Handler → Database/API → Response
```

### API Requests
```
Client → JWT Auth → Blueprint Route → Helper Function → Database/Cache → JSON Response
```

### WebSocket Events
```
Bot Event → WebSocket Server → Connected Clients → UI Update
```

---

## Security

### Authentication
- JWT tokens with automatic refresh
- Session tracking in SQLite
- Rate limiting on API endpoints

### Data Protection
- Config.py excluded from git (contains secrets)
- Environment variables for sensitive data
- Encrypted credentials for external APIs

### Access Control
- Admin-only endpoints for sensitive operations
- User role validation in Discord commands
- Permission checks before database modifications

---

## Performance

### Caching Strategy
- API responses cached with TTL (Time To Live)
- Rocket League stats: 5 minutes
- Warframe market data: 15 minutes
- Discord user data: 1 hour

### Database Optimization
- Indexed columns for frequent queries
- Connection pooling for API
- Prepared statements to prevent SQL injection

### Resource Management
- Async/await throughout for non-blocking I/O
- Connection limits for external APIs
- Automatic cleanup of old logs and cache

---

## Deployment

### Supported Platforms
- **Linux** - Primary deployment target
- **Docker** - Containerized deployment
- **Cloudflare Tunnel** - Secure external access

### Monitoring
- Rich console logging with colors
- Discord channel for bot logs
- API access logs
- Error tracking and alerts

See [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md) for detailed deployment instructions.
