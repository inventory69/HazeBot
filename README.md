# HazeBot 🌿

> **A feature-rich Discord bot with modular architecture and modern web interface**

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![Discord.py](https://img.shields.io/badge/discord.py-2.0%2B-blue.svg)](https://github.com/Rapptz/discord.py)
[![Flask](https://img.shields.io/badge/Flask-3.0%2B-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

HazeBot is a comprehensive Discord bot built with Python and discord.py, featuring modular cogs, RESTful API, and a modern Flutter admin panel. Originally designed for The Chillventory server, it is easily adaptable for any community.

## ✨ Key Features

- 🎮 **Gaming** - Rocket League stats with rank tracking & Warframe market integration
- 🎭 **Memes** - Daily automated memes + custom generator (100+ templates)
- 🎫 **Tickets** - Support system with email transcripts & auto-archiving
- 🛠️ **Moderation** - Interactive mod panel with warnings & channel controls
- 📝 **Management** - AI-powered changelogs, todo lists, welcome system
- 🌐 **REST API** - Modular Blueprint architecture (300 lines vs 6500)
- 📱 **Admin Panel** - Flutter cross-platform app with Material Design 3

**[📖 View Full Feature List](docs/FEATURES.md)**

---

## 🚀 Quick Start

### Option 1: Bot Only (Recommended for Testing)
```bash
# Clone and setup
git clone https://github.com/inventory69/HazeBot.git
cd HazeBot
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your DISCORD_BOT_TOKEN and DISCORD_GUILD_ID

# Configure server IDs
# Edit Config.py PROD_IDS dictionary with your channel/role IDs

# Run bot only (APIServer cog is automatically skipped)
python Main.py
```

### Option 2: Bot + API Server (Production with Admin Panel)
```bash
# After completing basic setup above, install API dependencies:
pip install -r api_requirements.txt

# Add API configuration to .env:
# API_PORT=5070
# SECRET_KEY=your-secret-key-here  # Generate: python -c "import secrets; print(secrets.token_hex(32))"
# API_ADMIN_USER=admin
# API_ADMIN_PASS=secure-password
# CORS_ORIGINS=https://your-domain.com,http://localhost:3000

# Run bot with API (loads APIServer cog automatically)
python start_with_api.py
```

**Note:** `Main.py` skips APIServer cog | `start_with_api.py` loads it

**📖 Detailed Instructions:** [docs/BOT_SETUP.md](docs/BOT_SETUP.md)  
**🔧 First Time?** Follow the [Complete Setup Guide](docs/BOT_SETUP.md) for step-by-step instructions

---

## 📦 What's Included

### 🎮 Gaming Integration
- **Rocket League** - Stats, rank tracking, auto rank-up notifications
- **Warframe** - Market prices, item search, live alerts/fissures/invasions

### 🎭 Meme System
- Automated daily posting from Reddit/Lemmy
- Custom generator with 100+ Imgflip templates
- Interactive creation with GUI configuration

### 🎫 Support & Moderation
- Interactive ticket system with real-time chat
- Admin panel integration with WebSocket updates
- Email transcripts and auto-archiving
- Smart push notifications (suppressed when viewing)
- Mod panel with mute/kick/ban/warn actions
- Message cache for instant loading

### 📊 Analytics System
- SQLite database with table partitioning
- Real-time session tracking and active user monitoring
- Interactive dashboard with charts (user growth, devices, features)
- JWT authentication with admin/mod access control
- REST API for metrics and session details
- Performance optimized (cached aggregates, indexed queries)
- **[📊 Analytics Documentation](analytics/README.md)**

### 🛠️ Bot Management
- 22 modular cogs with hot-reload
- API Server as loadable Cog (Port 5070)
- Rich logging (console + Discord channel)
- Smart caching with TTL

---

## 📚 Documentation

> **📋 [Complete Documentation Index](docs/README.md)** - Comprehensive guide to all documentation

### 🚀 Getting Started
- 📖 **[Features](docs/FEATURES.md)** - Complete feature list & commands
- 🔧 **[Bot Setup Guide](docs/BOT_SETUP.md)** - Discord bot installation & configuration
- 📋 **[Requirements](docs/REQUIREMENTS.md)** - Dependencies & system requirements
- ⚡ **[Quick Start](docs/QUICKSTART.md)** - Fast setup for development

### 🏗️ System Architecture
- 🏗️ **[Architecture](docs/ARCHITECTURE.md)** - Technical architecture & design patterns
- 🌐 **[REST API Documentation](api/README.md)** - Complete API reference with examples
- 📊 **[Analytics System](analytics/README.md)** - Analytics dashboard & tracking system

### 🔐 Authentication & Security
- 🔐 **[JWT Authentication Setup](analytics/ANALYTICS_JWT_SETUP.md)** - Secure authentication guide
- 📦 **[Analytics Deployment](analytics/DEPLOYMENT_SUMMARY.md)** - Analytics deployment checklist

### 📱 Client Applications
- 📱 **[HazeBot Admin Panel](https://github.com/inventory69/HazeBot-Admin)** - Flutter cross-platform app
- 🔧 **[Admin Panel Setup](docs/ADMIN_PANEL_SETUP.md)** - Flutter app configuration

### 🚢 Deployment & Operations
- 🚀 **[Deployment Checklist](docs/DEPLOYMENT_CHECKLIST.md)** - Production deployment guide
- 🌐 **[NGINX Configuration](docs/NGINX_NATIVE_CONFIG.md)** - Web server setup
- ☁️ **[Cloudflare Tunnel](docs/CLOUDFLARE_TUNNEL_CONFIG.md)** - Secure tunnel setup

### 🔧 Development
- 🤝 **[Contributing](docs/CONTRIBUTING.md)** - Development guidelines & code style
- 🔄 **[API with Bot](docs/API_WITH_BOT.md)** - Running API alongside bot

### 📊 Performance & Optimization
- ⚡ **[Performance Optimization](docs/PERFORMANCE_OPTIMIZATION.md)** - Speed improvements
- 🗄️ **[SQLite Migration Guide](docs/SQLITE_MIGRATION_GUIDE.md)** - Database migration
- 💾 **[Session Cache Improvements](docs/SESSION_CACHE_IMPROVEMENTS.md)** - Caching strategies

---

## 🔧 Requirements

- **Python 3.11+** - Modern Python release
- **discord.py 2.0+** - Discord API wrapper
- **Flask 3.0+** - Web framework
- **Discord Bot Token** - From [Discord Developer Portal](https://discord.com/developers/applications)

**Optional:** OpenAI API (AI formatting), FlareSolverr (Rocket League), SMTP (email transcripts)

**[📋 Full Requirements List](docs/REQUIREMENTS.md)**

---

## 🤝 Contributing

Contributions are welcome! See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines.

**Quick Steps:**
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/name`)
3. Make changes (follow `ruff` code style)
4. Test thoroughly
5. Submit a Pull Request

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details. Free to fork, modify, and use!

---

## 🙏 Acknowledgments

Built with 💖 for The Chillventory community

- Powered by [discord.py](https://github.com/Rapptz/discord.py)
- AI features by [OpenAI GPT](https://openai.com/)
- Special thanks to all contributors

**Questions?** Open an issue on GitHub or check the [documentation](docs/BOT_SETUP.md)!

*Made with 💖 for The Chillventory* 🌿
