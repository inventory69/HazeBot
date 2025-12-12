# HazeBot Copilot Instructions

## Architecture Overview

**HazeBot** is a modular Discord bot with REST API and real-time WebSocket communication. The codebase supports **dual-mode operation**:
- `Main.py` - Bot only (skips AnalyticsManager/APIServer cogs)
- `start_with_api.py` - Bot + API server (loads all cogs, runs Flask in separate thread)

### Project Structure
```
HazeBot/
├── Main.py / start_with_api.py    # Entry points (see above)
├── Config.py                       # Global constants, PROD_MODE, channel/role IDs
├── Cogs/                          # 24 modular cogs (discord.py extensions)
├── api/                           # Flask REST API (Blueprint architecture)
├── Utils/                         # Shared utilities (Logger, EmbedUtils, etc.)
├── Data/ vs TestData/             # Environment-based data dirs (PROD_MODE)
└── analytics/                     # SQLite analytics with dashboard
```

**Key Architectural Principle:** Config.py centralizes ALL environment-dependent settings (PROD_MODE, GUILD_ID, channel/role IDs). Cogs and API modules ONLY import from Config.py—never hardcode IDs.

## Critical Configuration System

### Dual Mode: Production vs Test
- **PROD_MODE** (Config.py) switches between production/test guilds, tokens, and data directories
- **PROD_IDS** / **TEST_IDS** dictionaries map logical names to Discord channel/role IDs
- Access IDs via `Config.CURRENT_IDS["channel_name"]` to get the correct value for current mode

### Config Persistence
- Runtime config changes (e.g., via `/config` commands or API) are saved to `Config_{guild_id}.json`
- `Utils/ConfigLoader.py` loads overrides on startup, modifying `Config.py` module attributes dynamically
- Example: `Config.RL_RANK_CHECK_INTERVAL_HOURS` starts at 24 but can be changed to 12 via admin UI

**When adding new config options:** 
1. Add default to `Config.py`
2. Add to `api/config_routes.py` GET/POST handlers
3. Add to `Utils/ConfigLoader.py` save/load logic

## Cog System (discord.py)

### Cog Loading Pattern
All cogs follow this structure:
```python
class MyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Start background tasks here

async def setup(bot: commands.Bot):
    await bot.add_cog(MyCog(bot))
```

Cogs are loaded in `Main.py`/`start_with_api.py` via:
```python
await bot.load_extension(f"Cogs.{cog_name}")
```

**Hot-reload support:** `/reload` command and `api/cog_routes.py` allow runtime reload without bot restart.

### Per-Cog Log Levels
`Config.COG_LOG_LEVELS` dictionary allows setting different log levels per cog (e.g., `{"RocketLeague": logging.DEBUG}`). Applied in `Utils/Logger.py`.

## API Architecture

### Blueprint Pattern
`api/app.py` is the main Flask app. Each feature area has its own Blueprint file:
- `auth_routes.py` - JWT auth, Discord OAuth2
- `ticket_routes.py` - Support ticket CRUD + WebSocket
- `rocket_league_routes.py` - RL stats, account linking
- `meme_routes.py` - Meme templates, generation
- `config_routes.py` - Bot configuration management
- `cog_routes.py` - Cog load/unload/reload
- `analytics.py` / `analytics_db.py` - Session tracking (SQLite)

**Integration:** APIServer cog (`Cogs/APIServer.py`) runs Flask app in a separate thread, exposing shared bot state to API via `app.bot_instance`.

### Authentication Flow
1. **Basic Auth:** Username/password → JWT token (48h expiry)
2. **Discord OAuth2:** User authorizes → callback receives code → exchange for token → verify guild membership and roles
3. **Roles:** Admin, Moderator, User (Lootling role in Discord)
4. JWT stored in Authorization header: `Bearer <token>`

### WebSocket (Tickets)
`api/ticket_routes.py` uses Flask-SocketIO for real-time ticket chat. Events:
- `join_ticket` - Client subscribes to ticket room
- `ticket_message` - Bidirectional chat (admin panel ↔ Discord)
- `ticket_closed` - Notify clients when ticket is closed

## Analytics System

### Storage: SQLite (preferred) or JSON (legacy)
- `Config.USE_SQLITE_ANALYTICS` (default: True) switches backends
- SQLite tables: `sessions`, `session_actions`, `active_sessions`
- **Partitioning:** Old data auto-moved to `sessions_YYYYMM` tables (see `api/analytics_partitioning.py`)

### Dashboard
Run `python analytics/view_analytics.py` to launch HTML dashboard at `http://localhost:8089`. Requires JWT auth (admin/mod only).

**Key metrics:** Active users (7d/30d), session duration, platform breakdown (Web/Android/iOS), feature usage by endpoint.

## Coding Conventions (Strictly Enforced)

### Imports & Comments
```python
# 📦 Built-in modules
import logging
from datetime import datetime

# 📥 Custom modules
from Config import GUILD_ID, PROD_MODE
from Utils.Logger import Logger
```
**Required:** Use emoji comment prefixes (`# 📦`, `# 📥`, `# 💡`, `# 🌱`) for section clarity.

### Naming & Style
- **PascalCase:** Classes, functions, variables, constants (`ThemeDict`, `InitLogging`, `UserCooldowns`)
- **Indentation:** TABS ONLY (no spaces)
- **Strings:** Single quotes always (`'message'`, not `"message"`)
- **F-strings:** Single quotes inside (`f'{name}'`)

### Sorting
- Imports: Longest to shortest (within each emoji section)
- Example: `from datetime import datetime` before `import logging`

## Development Workflows

### Local Development
```bash
# Bot only (no API dependencies)
python Main.py

# Bot + API (requires api_requirements.txt)
python start_with_api.py
```

**Environment Setup:**
1. Copy `.env.example` to `.env`
2. Set `PROD_MODE=false` for testing
3. Configure `TEST_DISCORD_BOT_TOKEN` and `DISCORD_TEST_GUILD_ID`
4. Edit `Config.py` `TEST_IDS` dictionary with test channel/role IDs

### Code Formatting
```fish
source .venv/bin/activate.fish
ruff format Cogs/        # Format all cogs
ruff check --fix .       # Auto-fix linting issues
```

**Note:** User's shell is Fish. Use Fish syntax for multi-command examples.

### Deployment
- **GitHub Actions:** Push to `main` triggers `/.github/workflows/deploy.yml`
- Restarts Pterodactyl bot server via API (see workflow for details)
- **Manual:** SSH to server, `git pull`, restart systemd service

## Common Patterns

### Creating New Cog
1. Create `Cogs/NewCog.py` with standard structure (see above)
2. Add emoji prefix to `Config.COG_PREFIXES` (e.g., `"NewCog": "🔧"`)
3. Optionally add to `Config.COG_LOG_LEVELS` for custom logging
4. Import Config.py constants—NEVER hardcode IDs

### Adding API Endpoint
1. Create or edit Blueprint in `api/{feature}_routes.py`
2. Use `@require_auth` decorator for protected routes
3. Import bot instance: `from api.app import app; bot = app.bot_instance`
4. Access Discord state: `bot.get_guild(Config.GUILD_ID)`, `bot.get_channel(...)`

### Ticket System Integration
- Discord: `Cogs/TicketSystem.py` creates tickets, manages channels
- API: `api/ticket_routes.py` provides REST + WebSocket for admin panel
- Both share `Data/tickets.json` (or `TestData/tickets.json`)
- WebSocket events keep admin panel in sync with Discord messages

## Testing Strategy

- **No formal test suite:** Manual testing in PROD_MODE=false environment
- **Test Guild:** Dedicated Discord server with matching channel/role structure
- **API Testing:** `analytics/test_api_endpoints.py` validates critical routes
- **Analytics:** `analytics/test_partitioning.py` validates database operations

## External Integrations

- **Rocket League:** tracker.gg API for stats, requires `ROCKET_LEAGUE_API_KEY`
- **Uptime Kuma:** Optional monitoring dashboard (`UPTIME_KUMA_URL` in .env)
- **Firebase:** Push notifications to mobile admin panel (`FCM_SERVER_KEY`)
- **Imgflip:** Meme generation API (public templates, no key needed)
- **Reddit/Lemmy:** Daily meme scraping (no auth, uses JSON APIs)

## Troubleshooting

### Cog Not Loading
- Check `COG_LOG_LEVELS` isn't suppressing errors
- Verify cog name matches filename (case-sensitive)
- Look for import errors in cog's `__init__` method

### Config Changes Not Persisting
- Ensure `Utils/ConfigLoader.py` includes new config key in `save_config_to_file()`
- Check `Config_{guild_id}.json` exists in Data/ or TestData/

### API 403 Errors
- Verify JWT token is valid (check expiry with jwt.io)
- Confirm user has required role (Admin/Moderator)
- Check Discord OAuth2 flow completed successfully

### Analytics Not Recording
- Verify `Config.USE_SQLITE_ANALYTICS = True`
- Check `Data/analytics.db` (or `TestData/analytics.db`) exists
- Review `api/analytics.py` `track_session()` calls in routes
