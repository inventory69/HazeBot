# Requirements 🔧

This document lists all requirements and dependencies for HazeBot.

## System Requirements

### Minimum
- **OS:** Linux, Windows, macOS
- **Python:** 3.11 or higher
- **RAM:** 100MB minimum
- **Storage:** 50MB for bot + 50MB for logs/cache
- **Network:** Stable internet connection

### Recommended
- **OS:** Linux (Ubuntu 20.04+ or Debian 11+)
- **Python:** 3.11 or higher
- **RAM:** 256MB or more
- **Storage:** 200MB+ for logs and cache
- **Network:** Low-latency connection (< 100ms to Discord)

---

## Core Dependencies

### Python Packages (Required)

```bash
# Install with: pip install -r requirements.txt
```

- **discord.py 2.0+** - Discord API wrapper
- **Flask 3.0+** - Web framework for REST API
- **python-dotenv** - Environment variable management
- **requests** - HTTP client for external APIs
- **aiohttp** - Async HTTP client
- **PyJWT** - JWT token handling
- **rich** - Rich console logging
- **Pillow** - Image processing for memes

### Python Packages (Optional)

- **openai** - For AI-powered changelog & todo formatting
- **gunicorn** - Production WSGI server for API
- **psutil** - System monitoring

---

## Optional Dependencies

### External Services

#### OpenAI API
**Purpose:** AI-powered formatting for changelogs and todo lists

**Setup:**
```bash
# Add to .env
OPENAI_API_KEY=sk-your-api-key-here
```

**Usage:**
- Changelog formatting with `/changelog format`
- Todo list emoji formatting with `/todo format`

---

#### FlareSolverr
**Purpose:** Bypass Cloudflare protection for Rocket League stats

**Setup:**
```bash
# Docker
docker run -d \
  --name=flaresolverr \
  -p 8191:8191 \
  ghcr.io/flaresolverr/flaresolverr:latest

# Add to .env
FLARESOLVERR_URL=http://localhost:8191
```

**Usage:**
- Rocket League stats with `/rlstats`
- Required for tracker.gg scraping

---

#### SMTP Server
**Purpose:** Send ticket transcripts via email

**Setup:**
```bash
# Add to .env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=your-email@gmail.com
```

**Usage:**
- Email transcripts when tickets are closed
- Automatic archiving with email backup

**Gmail App Password:**
1. Enable 2FA on your Google account
2. Go to https://myaccount.google.com/apppasswords
3. Generate app password for "Mail"
4. Use that password in `SMTP_PASSWORD`

---

#### Firebase (Admin Panel Only)
**Purpose:** Authentication and push notifications for Flutter admin panel

**Setup:** See [HazeBot-Admin FIREBASE_SETUP.md](https://github.com/inventory69/HazeBot-Admin/blob/main/FIREBASE_SETUP.md)

---

## API Keys

### Required
- **Discord Bot Token** - From https://discord.com/developers/applications
- **Discord Guild ID** - Your server ID (enable Developer Mode in Discord)

### Optional
- **OpenAI API Key** - From https://platform.openai.com/api-keys
- **Rocket League API** - FlareSolverr (see above)
- **Warframe Market API** - No key required (public API)

---

## Environment Setup

### Development

```bash
# Create virtual environment
python -m venv .venv

# Activate (Linux/macOS)
source .venv/bin/activate

# Activate (Windows)
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Edit .env with your tokens
nano .env
```

### Production

```bash
# Install system dependencies (Ubuntu/Debian)
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip

# Create dedicated user
sudo useradd -m -s /bin/bash hazebot

# Clone repository
sudo -u hazebot git clone https://github.com/inventory69/HazeBot.git /home/hazebot/HazeBot

# Setup environment
cd /home/hazebot/HazeBot
sudo -u hazebot python3.11 -m venv .venv
sudo -u hazebot .venv/bin/pip install -r requirements.txt

# Configure
sudo -u hazebot cp .env.example .env
sudo -u hazebot nano .env

# Optional: Install API dependencies
sudo -u hazebot .venv/bin/pip install -r api_requirements.txt
sudo -u hazebot .venv/bin/pip install gunicorn
```

---

## Port Requirements

### Bot Only
- No ports required (outbound connections only)

### Bot + API
- **5070** - Flask API (default, configurable in Config.py)
- **443** - HTTPS (if using reverse proxy)

### With Cloudflare Tunnel
- No ports required (tunnel handles routing)

---

## Database

### SQLite (Default)
- No installation required (built into Python)
- Database files stored in `Data/` directory
- Automatic creation on first run

### Files Created
- `Data/memes.db` - Meme tracking
- `Data/tickets.db` - Support tickets
- `Data/users.db` - User profiles
- `Data/warnings.db` - Moderation warnings

---

## Disk Space

### Typical Usage
- **Bot files:** ~10MB
- **Dependencies:** ~40MB
- **Logs:** 5-20MB per month
- **Cache:** 10-50MB (auto-cleaned)
- **Databases:** 5-50MB (depends on usage)

### Recommendations
- **Minimum:** 100MB free
- **Recommended:** 500MB+ free
- **Production:** 1GB+ free for growth

---

## Network

### Bandwidth
- **Idle:** < 1KB/s
- **Active:** 10-50KB/s
- **Heavy load:** 100-500KB/s

### Endpoints
- **Discord API:** wss://gateway.discord.gg
- **Tracker.gg:** https://tracker.gg (Rocket League)
- **Warframe Market:** https://api.warframe.market
- **OpenAI API:** https://api.openai.com (optional)

---

## Troubleshooting

### Python Version
```bash
# Check Python version
python --version  # Should be 3.11+

# If wrong version, specify
python3.11 --version
```

### Missing Dependencies
```bash
# Reinstall all dependencies
pip install --upgrade -r requirements.txt

# Check installed packages
pip list
```

### Permission Issues
```bash
# Fix permissions (Linux)
sudo chown -R hazebot:hazebot /home/hazebot/HazeBot
sudo chmod -R 755 /home/hazebot/HazeBot
```

### Port Already in Use
```bash
# Check what's using port 5070
sudo lsof -i :5070

# Kill process if needed
sudo kill -9 <PID>
```

---

## Next Steps

- 📖 [Bot Setup Guide](BOT_SETUP.md) - Discord bot installation & configuration
- 📱 [Admin Panel Setup](ADMIN_PANEL_SETUP.md) - Web/mobile interface setup
- 🏗️ [Architecture](ARCHITECTURE.md) - Technical architecture details
- 🚀 [Deployment](DEPLOYMENT_CHECKLIST.md) - Production deployment
