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

```bash
# Clone and setup
git clone https://github.com/inventory69/HazeBot.git
cd HazeBot
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your Discord token

# Run
python Main.py                 # Bot only
python start_with_api.py       # Bot + API (Port 5070)
```

**📖 Detailed Instructions:** [docs/BOT_SETUP.md](docs/BOT_SETUP.md)

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
- SQLite-based session tracking
- Real-time user monitoring
- Export to JSON with date filtering
- Performance metrics and caching
- 30-day data retention

### 🛠️ Bot Management
- 22 modular cogs with hot-reload
- API Server as loadable Cog (Port 5070)
- Rich logging (console + Discord channel)
- Smart caching with TTL

---

## 📚 Documentation

- 📖 **[Features](docs/FEATURES.md)** - Complete feature list & commands
- 🔧 **[Bot Setup Guide](docs/BOT_SETUP.md)** - Discord bot installation & configuration
- 🏗️ **[Architecture](docs/ARCHITECTURE.md)** - Technical architecture & structure
- 📋 **[Requirements](docs/REQUIREMENTS.md)** - Dependencies & system requirements
- 🌐 **[REST API](api/README.md)** - REST API endpoints & Blueprint details
- 📱 **[Admin Panel](https://github.com/inventory69/HazeBot-Admin)** - Flutter app setup & documentation
- 🚀 **[Deployment](docs/DEPLOYMENT_CHECKLIST.md)** - Production deployment
- 🤝 **[Contributing](docs/CONTRIBUTING.md)** - Development guidelines

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
