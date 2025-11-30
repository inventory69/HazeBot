# HazeBot Setup Guide 🚀

Complete guide for setting up HazeBot Discord bot with or without API integration.

---

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Option 1: Bot Only (No API)](#option-1-bot-only-no-api)
- [Option 2: Bot + API (With Admin Panel)](#option-2-bot--api-with-admin-panel)
- [Environment Variables](#environment-variables)
- [Optional Services](#optional-services)
- [Troubleshooting](#troubleshooting)

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

Edit `Config.py` to customize:

```python
# Guild & Channel IDs
GUILD_ID = 123456789  # Your server ID
LOG_CHANNEL_ID = 123456789  # Bot logs
MEME_CHANNEL_ID = 123456789  # Daily memes
TICKET_CATEGORY_ID = 123456789  # Support tickets

# Role IDs
ADMIN_ROLE_ID = 123456789
MODERATOR_ROLE_ID = 123456789

# Feature Toggles
ENABLE_DAILY_MEME = True
ENABLE_TICKETS = True
ENABLE_ROCKET_LEAGUE = True
```

💡 **Tip:** Use Discord Developer Mode to copy IDs (Right-click → Copy ID)

### Step 7: Run the Bot

```bash
python Main.py
```

You should see:
```
🤖 Bot is ready!
Logged in as: HazeBot#1234
Connected to 1 guild
22 cogs loaded
```

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
API_SECRET_KEY=your-very-secret-key-change-in-production

# Admin Credentials
API_ADMIN_USER=admin
API_ADMIN_PASS=your_secure_password_here

# Additional users (optional, format: username:password,username2:password2)
API_EXTRA_USERS=moderator:pass123,user:pass456

# Debug Mode (false in production!)
API_DEBUG=false
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
🤖 Starting HazeBot with API integration...
✅ Discord bot started
🌐 API server starting on port 5070
 * Running on http://0.0.0.0:5070
📡 WebSocket server ready
```

### Step 11: Verify API is Running

```bash
# Test API health endpoint
curl http://localhost:5070/api/health

# Expected response:
{"status": "ok", "bot_connected": true}
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

```env
# ============================================================================
# DISCORD CONFIGURATION
# ============================================================================
DISCORD_BOT_TOKEN=your_discord_bot_token_here
DISCORD_GUILD_ID=your_guild_id_here

# ============================================================================
# ROCKET LEAGUE (Optional)
# ============================================================================
ROCKET_API_BASE=https://api_url_of_your_choice
ROCKET_API_KEY=your_rocket_api_key_here
FLARESOLVERR_URL=https://your_flaresolverr_url_here  # For bypassing Cloudflare

# ============================================================================
# EMAIL / SMTP (Optional - for ticket transcripts)
# ============================================================================
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=465
SMTP_USER=your_email@gmail.com
SMTP_PASS=your_app_password
SUPPORT_EMAIL=support@example.com

# ============================================================================
# OPENAI (Optional - for AI changelog generation)
# ============================================================================
OPENAI_API_KEY=sk-...

# ============================================================================
# API CONFIGURATION (Only needed for Option 2)
# ============================================================================
API_PORT=5070
API_SECRET_KEY=change-this-to-a-random-string
API_ADMIN_USER=admin
API_ADMIN_PASS=secure_password
API_EXTRA_USERS=
API_DEBUG=false

# ============================================================================
# FIREBASE (Optional - for mobile push notifications)
# ============================================================================
FIREBASE_CREDENTIALS=firebase-credentials.json
```

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
✅ Loaded: Cog.DailyMeme
❌ Failed to load: Cog.RocketLeague (missing dependencies)
```

**Reload a specific cog:**
```discord
!reload CogName
```

**List all cogs:**
```discord
!listcogs
```

### API not accessible

**Error: `Connection refused` when accessing API**
- ✅ Make sure you started with `python start_with_api.py` not `python Main.py`
- ✅ Check firewall allows port 5070
- ✅ Verify API_PORT in `.env` matches

**From mobile device:**
- Use your PC's local IP (not localhost)
- Find IP: `ip addr show` (Linux) or `ipconfig` (Windows)
- Example: `http://192.168.1.100:5070/api`

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

| File | Purpose |
|------|---------|
| `Main.py` | Start bot only (no API) |
| `start_with_api.py` | Start bot + API server |
| `Config.py` | Bot configuration (IDs, settings) |
| `.env` | Secrets & environment variables |
| `Cogs/` | Modular bot features |
| `api/` | Flask API for admin panel |

**Need help?** Open an issue on [GitHub](https://github.com/inventory69/HazeBot/issues) or check the [documentation](README.md)!

---

*Made with 💖 for The Chillventory* 🌿
