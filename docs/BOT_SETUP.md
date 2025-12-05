# HazeBot Setup Guide 🚀

Complete guide for setting up HazeBot Discord bot with or without API integration.

---

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Choosing Your Setup Mode](#choosing-your-setup-mode)
- [Option 1: Bot Only (No API)](#option-1-bot-only-no-api)
- [Option 2: Bot + API (With Admin Panel)](#option-2-bot--api-with-admin-panel)
- [Environment Variables](#environment-variables)
- [Optional Services](#optional-services)
- [Troubleshooting](#troubleshooting)

---

## Choosing Your Setup Mode

HazeBot can run in two modes:

| Mode | File | Loads APIServer Cog? | Use Case |
|------|------|---------------------|----------|
| **Bot Only** | `Main.py` | ❌ No | Testing, development, or Discord-only features |
| **Bot + API** | `start_with_api.py` | ✅ Yes | Production with web/mobile admin panel |

**Key Differences:**
- `Main.py` - Automatically skips APIServer cog, no Flask/API dependencies needed
- `start_with_api.py` - Loads APIServer as a cog, enables REST API + WebSocket

**Recommended:**
- Start with `Main.py` for testing
- Switch to `start_with_api.py` for production with admin panel

---

## Prerequisites

### Required
- **Python 3.11+** - [Download](https://www.python.org/downloads/)
- **Discord Bot Token** - [Get from Discord Developer Portal](https://discord.com/developers/applications)
- **Discord Guild (Server) ID** - Enable Developer Mode in Discord → Right-click server → Copy ID

### Recommended
- **Git** - For cloning the repository
- **Virtual Environment** - Keeps dependencies isolated

---

## Option 1: Bot Only (No API)

Perfect for running just the Discord bot without web interface or admin panel.

### Step 1: Clone Repository

```bash
git clone https://github.com/inventory69/HazeBot.git
cd HazeBot
```

### Step 2: Create Virtual Environment

```bash
# Linux/macOS
python3 -m venv .venv
source .venv/bin/activate

# Windows
python -m venv .venv
.venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

**Core Dependencies:**
- `discord.py` - Discord API wrapper
- `aiohttp` - Async HTTP client
- `python-dotenv` - Environment variable management
- See [REQUIREMENTS.md](REQUIREMENTS.md) for full list

### Step 4: Create Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **New Application** → Enter name (e.g., "HazeBot")
3. Go to **Bot** tab → Click **Add Bot**
4. Under **Token**, click **Reset Token** → Copy it (save securely!)
5. Enable these **Privileged Gateway Intents**:
   - ✅ Server Members Intent
   - ✅ Message Content Intent
   - ✅ Presence Intent
6. Go to **OAuth2 → URL Generator**
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: `Administrator` (or customize)
   - Copy generated URL and invite bot to your server

### Step 5: Configure Environment

```bash
cp .env.example .env
nano .env  # or use any text editor
```

**Minimum required variables:**

```env
# Discord Configuration
DISCORD_BOT_TOKEN=your_discord_bot_token_here
DISCORD_GUILD_ID=your_guild_id_here
```

**Optional but recommended:**

```env
# Rocket League (for RL cog)
ROCKET_API_BASE=https://api.example.com
ROCKET_API_KEY=your_key

# Email (for ticket transcripts)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=465
SMTP_USER=your@email.com
SMTP_PASS=your_password
SUPPORT_EMAIL=support@example.com

# OpenAI (for AI changelog generation)
OPENAI_API_KEY=sk-...
```

### Step 6: Configure Bot Settings

HazeBot uses `Config.py` for channel/role IDs and feature settings. Most configuration is done via `.env`, but you need to update IDs in `Config.py`:

**Edit `Config.py`** and update the `PROD_IDS` dictionary (lines 161-203):

```python
PROD_IDS = {
    # Role IDs
    "ADMIN_ROLE_ID": 123456789,           # Admin role
    "MODERATOR_ROLE_ID": 987654321,       # Moderator role
    "NORMAL_ROLE_ID": 111222333,          # Normal member role
    "MEMBER_ROLE_ID": 444555666,          # Member role
    "CHANGELOG_ROLE_ID": 777888999,       # Changelog notification role
    "MEME_ROLE_ID": 123123123,            # Meme notification role (optional)
    
    # Channel IDs
    "LOG_CHANNEL_ID": 111111111,          # Bot logging channel
    "CHANGELOG_CHANNEL_ID": 222222222,    # Changelog posts
    "TODO_CHANNEL_ID": 333333333,         # Todo list channel
    "RL_CHANNEL_ID": 444444444,           # Rocket League stats
    "MEME_CHANNEL_ID": 555555555,         # Daily memes (optional)
    "SERVER_GUIDE_CHANNEL_ID": 666666666, # Server guide (optional)
    "GAMING_CHANNEL_ID": 777777777,       # Gaming channel (optional)
    "WELCOME_RULES_CHANNEL_ID": 888888888,# Welcome/rules channel
    "WELCOME_PUBLIC_CHANNEL_ID": 999999999,# Public welcome channel
    "TICKETS_CATEGORY_ID": 101010101,     # Support tickets category
    "TRANSCRIPT_CHANNEL_ID": 121212121,   # Ticket transcripts
    
    # Additional Configuration
    "INTEREST_ROLE_IDS": [],              # Interest role IDs (optional)
    "INTEREST_ROLES": {},                 # Interest role names (optional)
}
```

**Important Settings in `Config.py`:**
```python
# Lines 89-93: Bot behavior
BotName = "Haze World Bot"
CommandPrefix = "!"
PresenceUpdateInterval = 3600  # seconds between presence updates
MessageCooldown = 5  # seconds between user messages
FuzzyMatchingThreshold = 0.6  # command matching sensitivity

# Lines 481-483: Rocket League settings
RL_RANK_CHECK_INTERVAL_HOURS = 3  # How often to check ranks
RL_RANK_CACHE_TTL_SECONDS = 10500  # Cache duration

# Lines 569-595: Meme system (auto-loaded from Data/ files)
DEFAULT_MEME_SUBREDDITS = ["memes", "dankmemes", ...]
DEFAULT_MEME_LEMMY = ["196@lemmy.blahaj.zone", ...]
MEME_TEMPLATES_CACHE_DURATION = 86400  # 24 hours
```

💡 **Tips:** 
- Use Discord Developer Mode to copy IDs (Right-click → Copy ID)
- Most IDs can stay at defaults if you don't use that feature
- Use `TEST_IDS` dictionary (lines 204-246) for test server configuration
- Set `PROD_MODE=false` in `.env` to use TEST_IDS instead of PROD_IDS

### Step 7: Run the Bot

```bash
python Main.py
```

You should see:
```
🚀 Starting Cog loading sequence...
   └─ ⏭️ Skipped: AnalyticsManager (requires API - use start_with_api.py)
   └─ ✅ Loaded: CogManager
   └─ ✅ Loaded: DiscordLogging
   └─ ✅ Loaded: General
   └─ ✅ Loaded: Moderation
   ... (more cogs)
🧩 All Cogs loaded: CogManager, DiscordLogging, General, ...
🔗 Synced 15 guild slash commands.
🤖 HazeWorldBot starting in PRODUCTION mode
HazeBot is online as HazeBot#1234!
```

**Note:** AnalyticsManager and APIServer are automatically skipped in bot-only mode (use `start_with_api.py` for full features).

### Step 8: Test Basic Commands

In Discord:
```
!help           - Show all commands
!ping           - Test bot responsiveness
!listcogs       - Show loaded cogs
!reload <cog>   - Reload a cog (admin only)
```

✅ **Bot-only setup complete!** The bot is now running with all Discord features.

---

## Option 2: Bot + API (With Admin Panel)

Includes Flask API for web/mobile admin panel with advanced management features.

### Step 1-6: Complete Bot Setup First

Follow all steps from **Option 1** above to get the base bot running.

### Step 7: Install API Dependencies

```bash
pip install -r api_requirements.txt
```

**Additional Dependencies:**
- `Flask` - Web framework
- `Flask-CORS` - Cross-origin requests
- `PyJWT` - JWT authentication
- `Flask-SocketIO` - Real-time WebSocket communication
- `firebase-admin` - Push notifications (optional)

### Step 8: Configure API Settings

Add to your `.env` file:

```env
# ============================================================================
# API CONFIGURATION
# ============================================================================

# API Port (5070 recommended to avoid conflicts)
API_PORT=5070

# JWT Secret Key (generate with: python -c "import secrets; print(secrets.token_hex(32))")
SECRET_KEY=your-very-secret-key-change-in-production

# Admin Credentials
API_ADMIN_USER=admin
API_ADMIN_PASS=your_secure_password_here

# Additional users (optional, format: username:password,username2:password2)
API_EXTRA_USERS=moderator:pass123,user:pass456

# CORS Origins (comma-separated, for web/mobile access)
CORS_ORIGINS=https://your-domain.com,http://localhost:3000

# Discord OAuth2 (optional, for Discord login in admin panel)
DISCORD_CLIENT_ID=your_client_id
DISCORD_CLIENT_SECRET=your_client_secret
DISCORD_REDIRECT_URI=https://your-domain.com/api/discord/callback

# Firebase Cloud Messaging (optional, for push notifications)
FCM_SERVER_KEY=your_fcm_server_key
```

### Step 9: Firebase Setup (Optional - for Push Notifications)

Only needed if you want mobile push notifications in the admin panel.

1. Create Firebase project at [Firebase Console](https://console.firebase.google.com/)
2. Download `firebase-credentials.json` from Project Settings → Service Accounts
3. Place file in HazeBot root directory
4. See [HazeBot-Admin FIREBASE_SETUP.md](https://github.com/inventory69/HazeBot-Admin/blob/main/FIREBASE_SETUP.md) for full instructions

```env
# Add to .env (optional)
FIREBASE_CREDENTIALS=firebase-credentials.json
```

### Step 10: Start Bot + API

```bash
python start_with_api.py
```

You should see:
```
🚀 Starting Cog loading sequence...
   └─ ✅ Loaded: AnalyticsManager
   └─ ✅ Loaded: APIServer
   └─ ✅ Loaded: CogManager
   └─ ✅ Loaded: DiscordLogging
   ... (more cogs)
🧩 All Cogs loaded: AnalyticsManager, APIServer, CogManager, ...
🔗 Synced 15 guild slash commands.
🌐 API Server: Starting Flask app on 0.0.0.0:5070
 * Running on http://0.0.0.0:5070
📡 WebSocket server ready
🤖 Starting Discord bot (API will start via APIServer cog)...
HazeBot is online as HazeBot#1234!
```

**Note:** API is now loaded as a Cog (APIServer) and starts automatically with the bot.

### Step 11: Verify API is Running

```bash
# Test API health endpoint
curl http://localhost:5070/api/health

# Expected response:
{"status": "ok", "timestamp": "2024-12-05T10:30:00Z"}

# Test authentication
curl -X POST http://localhost:5070/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your_password"}'

# Expected response:
{"token": "eyJ...", "user": "admin", "role": "admin"}
```

### Step 12: Setup Admin Panel (Optional)

To use the Flutter web/mobile interface:

**Quick Links:**
- 📱 **[HazeBot-Admin Repository](https://github.com/inventory69/HazeBot-Admin)**
- 📖 **[Admin Panel Setup Guide](ADMIN_PANEL_SETUP.md)**
- 🚀 **[Download Android APK](https://github.com/inventory69/HazeBot-Admin/releases/latest)**

**Quick Start:**
```bash
# Clone admin panel
git clone https://github.com/inventory69/HazeBot-Admin.git
cd HazeBot-Admin

# Install Flutter dependencies
flutter pub get

# Configure API URL
cp .env.example .env
nano .env  # Set API_BASE_URL=http://localhost:5070/api

# Run web interface
flutter run -d chrome

# Or build Android APK
flutter build apk --release
```

Full instructions: [ADMIN_PANEL_SETUP.md](ADMIN_PANEL_SETUP.md)

✅ **Bot + API setup complete!** You can now manage HazeBot via web/mobile interface.

---

## Environment Variables

### Complete `.env` Template

**Legend:**
- ✅ **Required** - Must be set for basic functionality
- 📱 **Optional** - Enables specific features
- 🌐 **API Only** - Only needed when running `start_with_api.py`

```env
# ============================================================================
# DISCORD CONFIGURATION ✅ (Required for both modes)
# ============================================================================
DISCORD_BOT_TOKEN=your_discord_bot_token_here
DISCORD_GUILD_ID=your_guild_id_here

# Optional: Test mode configuration (set PROD_MODE=false to use these)
TEST_DISCORD_BOT_TOKEN=your_test_bot_token
DISCORD_TEST_GUILD_ID=your_test_guild_id
DISCORD_TEST_GUILD_NAME=Test Server Name

# Production mode toggle (default: false)
PROD_MODE=true

# ============================================================================
# ANALYTICS 📱 (Optional - set backend type)
# ============================================================================
ANALYTICS_BACKEND=sqlite  # Options: sqlite (default), json
TIMEZONE=Europe/Berlin    # Timezone for analytics

# ============================================================================
# ROCKET LEAGUE 📱 (Optional - for RL stats tracking)
# ============================================================================
ROCKET_API_BASE=https://api.tracker.gg
ROCKET_API_KEY=your_rocket_api_key_here
FLARESOLVERR_URL=http://localhost:8191  # For bypassing Cloudflare

# ============================================================================
# EMAIL / SMTP 📱 (Optional - for ticket transcripts)
# ============================================================================
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=465
SMTP_USER=your_email@gmail.com
SMTP_PASS=your_app_password_here
SUPPORT_EMAIL=support@yourdomain.com

# ============================================================================
# OPENAI 📱 (Optional - for AI changelog generation)
# ============================================================================
OPENAI_API_KEY=sk-proj-...

# ============================================================================
# IMGFLIP 📱 (Optional - for meme template generation)
# ============================================================================
IMGFLIP_USERNAME=your_imgflip_username
IMGFLIP_PASSWORD=your_imgflip_password

# ============================================================================
# API CONFIGURATION 🌐 (Only needed with start_with_api.py)
# ============================================================================
API_PORT=5070

# JWT Secret Key (generate with: python -c "import secrets; print(secrets.token_hex(32))")
SECRET_KEY=change-this-to-a-random-string-use-secrets-token-hex-32

# Admin Credentials
API_ADMIN_USER=admin
API_ADMIN_PASS=secure_password_change_in_production

# Additional users (format: username:password,username2:password2)
API_EXTRA_USERS=moderator:pass123,user:pass456

# CORS Origins (comma-separated, for web/mobile access)
CORS_ORIGINS=https://your-domain.com,http://localhost:3000,http://192.168.1.100:3000

# Discord OAuth2 (optional, for Discord login in admin panel)
DISCORD_CLIENT_ID=your_client_id
DISCORD_CLIENT_SECRET=your_client_secret
DISCORD_REDIRECT_URI=https://your-domain.com/api/discord/callback

# Discord Role IDs (for API access control)
ADMIN_ROLE_ID=123456789
MODERATOR_ROLE_ID=987654321
LOOTLING_ROLE_ID=111222333  # Regular user role

# ============================================================================
# FIREBASE 🌐 (Optional - for mobile push notifications with API)
# ============================================================================
FIREBASE_CREDENTIALS=firebase-credentials.json
FCM_SERVER_KEY=your_fcm_server_key
```

**Priority Setup:**
1. **Minimum (Bot only)**: `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`
2. **With API**: Add `API_PORT`, `SECRET_KEY`, `API_ADMIN_USER`, `API_ADMIN_PASS`
3. **Full features**: Add optional services as needed (RL, OpenAI, SMTP, etc.)

---

## Optional Services

### OpenAI API (AI Changelog Generation)

**What it does:** Automatically formats changelogs with GPT-4 Turbo

**Setup:**
1. Get API key from [OpenAI Platform](https://platform.openai.com/api-keys)
2. Add to `.env`: `OPENAI_API_KEY=sk-...`
3. Use `!changelog` command with AI formatting

**Cost:** ~$0.01 per changelog (uses GPT-4 Turbo)

### FlareSolverr (Rocket League Stats)

**What it does:** Bypasses Cloudflare protection for RL API scraping

**Setup:**
```bash
# Docker (recommended)
docker run -d \
  --name=flaresolverr \
  -p 8191:8191 \
  ghcr.io/flaresolverr/flaresolverr:latest

# Add to .env
FLARESOLVERR_URL=http://localhost:8191
```

**Alternative:** Use official Rocket League API if available

### SMTP Email (Ticket Transcripts)

**What it does:** Sends ticket transcripts via email when closed

**Setup for Gmail:**
1. Enable 2FA on Google Account
2. Generate App Password: Account → Security → 2-Step Verification → App Passwords
3. Add to `.env`:
```env
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=465
SMTP_USER=your.email@gmail.com
SMTP_PASS=your_app_password_here
SUPPORT_EMAIL=support@yourdomain.com
```

---

## Troubleshooting

### Bot won't start

**Error: `discord.errors.LoginFailure: Improper token has been passed`**
- ✅ Check `DISCORD_BOT_TOKEN` in `.env` is correct
- ✅ Token should start with `MTk...` or similar
- ✅ Regenerate token in Discord Developer Portal if needed

**Error: `Guild not found`**
- ✅ Verify `DISCORD_GUILD_ID` matches your server
- ✅ Enable Developer Mode in Discord → Right-click server → Copy ID
- ✅ Make sure bot is invited to the server

### Cogs not loading

**Check loaded cogs:**
```bash
# In bot logs, look for:
   └─ ✅ Loaded: DailyMeme
   └─ ❌ Failed to load RocketLeague: No module named 'rlapi'
   └─ ⏸️ Skipped (disabled): TestCog
```

**Common reasons:**
- Missing dependencies (install with `pip install -r requirements.txt`)
- Cog is persistently disabled (use `!enablecog CogName` to re-enable)
- Python syntax error in cog file

**Manage cogs:**
```discord
!listcogs              # Show all cogs and their status
!reload CogName        # Reload a specific cog
!disablecog CogName    # Persistently disable a cog
!enablecog CogName     # Re-enable a disabled cog
```

**Note:** In bot-only mode (`Main.py`), APIServer cog is automatically skipped.

### API not accessible

**Error: `Connection refused` when accessing API**
- ✅ Make sure you started with `python start_with_api.py` (not `python Main.py`)
- ✅ Look for `✅ Loaded: APIServer` in startup logs
- ✅ Check firewall allows port 5070
- ✅ Verify `API_PORT` in `.env` matches (default: 5070)

**Error: `401 Unauthorized` when accessing endpoints**
- ✅ Obtain JWT token via `/api/auth/login` endpoint
- ✅ Include token in header: `Authorization: Bearer <token>`
- ✅ Check username/password in `.env` (API_ADMIN_USER, API_ADMIN_PASS)

**From mobile device:**
- Use your PC's local IP (not localhost)
- Find IP: `ip addr show` (Linux) or `ipconfig` (Windows)
- Example: `http://192.168.1.100:5070/api`
- Make sure `CORS_ORIGINS` in `.env` includes your access URL

**WebSocket not connecting:**
- ✅ Use `wss://` for HTTPS or `ws://` for HTTP
- ✅ Include JWT token in connection auth object
- ✅ Check browser console for specific error messages

### Permission errors

**Bot can't send messages / create channels:**
- ✅ Bot needs `Administrator` permission (or specific permissions)
- ✅ Re-invite bot with correct permissions from OAuth2 URL

---

## Next Steps

- 📖 **[Features Guide](FEATURES.md)** - Complete command reference
- 🏗️ **[Architecture](ARCHITECTURE.md)** - Understanding the cog system
- 📱 **[Admin Panel Setup](ADMIN_PANEL_SETUP.md)** - Web/mobile interface
- 🚀 **[Deployment Guide](DEPLOYMENT_CHECKLIST.md)** - Production deployment
- 🤝 **[Contributing](CONTRIBUTING.md)** - Development guidelines

---

## Quick Reference

### File Structure

| File/Folder | Purpose |
|-------------|---------|
| `Main.py` | Start bot only (no API) - skips APIServer cog |
| `start_with_api.py` | Start bot + API server - loads APIServer cog |
| `Config.py` | Bot configuration (IDs, settings, feature toggles) |
| `.env` | Secrets & environment variables (tokens, passwords) |
| `Cogs/` | Modular bot features (22 cogs) |
| `api/` | Flask API for admin panel (REST + WebSocket) |
| `Data/` | Production data (JSON/SQLite files) |
| `TestData/` | Test mode data (when PROD_MODE=false) |
| `Utils/` | Helper functions and utilities |

### Config.py Key Sections

| Lines | Section | Description |
|-------|---------|-------------|
| 25-46 | Environment | `PROD_MODE`, `BOT_TOKEN`, `GUILD_ID`, `DATA_DIR` |
| 89-93 | Bot Behavior | `BotName`, `CommandPrefix`, `MessageCooldown` |
| 161-203 | PROD_IDS | Production server channel/role IDs |
| 204-246 | TEST_IDS | Test server channel/role IDs |
| 254-286 | ID Exports | Exports correct IDs based on PROD_MODE |
| 294-318 | Slash Commands | List of commands with slash (/) support |
| 392-426 | Server Guide | Server guide configuration |
| 431-476 | Welcome System | Rules, messages, button replies |
| 477-564 | Rocket League | Rank tracking, emojis, congrats messages |
| 565-604 | Meme System | Subreddits, Lemmy communities, templates |

### Configuration Priority

**1. Required (.env)**
- `DISCORD_BOT_TOKEN` - Bot authentication
- `DISCORD_GUILD_ID` - Server ID

**2. Required (Config.py PROD_IDS)**
- All channel IDs and role IDs for your server

**3. Optional Features**
- Enable in `.env` as needed (RL, OpenAI, SMTP, etc.)
- Configure in `Config.py` for feature-specific settings

**Need help?** Open an issue on [GitHub](https://github.com/inventory69/HazeBot/issues) or check the [documentation](../README.md)!

---

*Made with 💖 for The Chillventory* 🌿
