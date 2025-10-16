# HazeWorldBot 🌿

# ⚠️ **IMPORTANT: PERSONAL USE ONLY**

**This project is intended exclusively for personal use by the developer and is not designed for public use, redistribution, or commercial purposes.**

*(Dieses Projekt ist ausschließlich für den persönlichen Gebrauch des Entwicklers bestimmt und nicht für die öffentliche Nutzung, Weiterverbreitung oder kommerzielle Verwendung gedacht.)*

---

A personal Discord bot designed for The Chillventory server ("Haze" on Discord). Built with Python and discord.py, HazeWorldBot enhances moderation, onboarding, changelogs, and community engagement with a modular, inventory-themed experience.

---

## ✨ Features

### 🛠️ Utility & Moderation
- **Prefix & Slash Commands:** Both `!` and `/` commands for all major features.
- **Help System:** `/help` and `!help` show all commands, with mod/admin commands only visible to authorized users.
- **Status:** `/status` and `!status` display bot latency and server count.
- **Message Management:** `!clear` for admins and Slot Keepers (mods) to purge messages.
- **Say Command:** `!say` lets admins send bot messages (with embed option).
- **Mod Panel:** `/modpanel` and `!modpanel` for Slot Keepers and Admins to select users and perform moderation actions (Mute, Kick, Ban, Warn with optional reason), lock channels, and set slowmode. Warnings are tracked per user and stored in `Data/mod_data.json`.
- **Mod Details:** `/moddetails` and `!moddetails` for Slot Keepers and Admins to view detailed moderation history for specific users.
- **Centralized Command Lists:** All admin/mod commands are managed in `Config.py` for consistency.

### 🎫 Ticket System
- **Create Tickets:** `/ticket` and `!ticket` for support, bugs, or applications.
- **Interactive Controls:** Claim, assign, close, and reopen tickets with buttons.
- **Role-Based Permissions:** Slot Keepers (mods) and Admins can claim/close; only Admins can assign.
- **Transcript & Email:** Closed tickets generate transcripts and can send via email.
- **Automatic Cleanup:** Old tickets are deleted after 7 days.

### 🚀 Rocket League Integration
- **Stats Fetching:** `/rlstats` and `!rlstats` show player stats for 1v1, 2v2, 3v3, 4v4.
- **Account Linking:** `/setrlaccount` and `!setrlaccount` to save your RL account.
- **Rank Promotion Notifications:** Automatic notifications and congratulation embeds for rank-ups.
- **Performance Caching:** API calls are cached for 1 hour to reduce external requests and improve response times.

### 📝 Changelog System
- **Automated Changelog Generation:** `!changelog` uses GPT-4 Turbo to format PR/commit text as Discord embeds.
- **Post to Channel Button:** Instantly post changelogs to the designated channel with a notification.
- **Role Mention:** Changelog notification role can be toggled by users in preferences.

### 📦 Role Info
- **Role Descriptions:** `/roleinfo` and `!roleinfo` show readable info, permissions, and usage tips for Admin, Slot Keeper (mod), and Lootling (member) roles.
- **Autocomplete:** Only main roles selectable in slash command.
- **Command List:** Shows relevant commands for each role.

### 🛠️ Preferences System
- **Changelog Notification Opt-In:** `/preferences` and `!preferences` let users toggle the changelog notification role.

### 👤 Profile System
- **User Profiles:** `/profile` and `!profile` display user avatar, join date, roles, highest RL rank, warnings, resolved tickets, changelog opt-in, and activity stats (messages/images).
- **Activity Tracking:** Automatically tracks message and image posting activity.

### 🏆 Leaderboard System
- **Various Leaderboards:** `/leaderboard` and `!leaderboard` with categories for RL ranks (overall/1v1/2v2/3v3/4v4), resolved tickets, most messages, and most images posted.
- **Real-time Updates:** Activity data is cached for 30 seconds for optimal performance.

### 🎮 Dynamic Presence
- **Inventory-Themed Status:** Bot presence updates hourly with fun inventory messages and emojis.

### 🎉 Welcome System
- **Interactive Rule Acceptance:** New members select interests and accept rules via dropdown and button.
- **Polished Welcome Cards:** Personalized welcome embeds with inventory vibes.
- **Persistent Welcome Buttons:** Community can greet new members with themed replies.
- **Automatic Cleanup:** Welcome messages are deleted when members leave.

### ⚡ Performance & Caching
- **Advanced Caching System:** Custom-built caching utilities with in-memory and file-based caching for optimal performance.
- **Optimized Data Loading:** All data operations use async caching with configurable TTL to reduce I/O operations.
- **Reduced API Calls:** External API requests are intelligently cached to minimize rate limiting and improve response times.
- **Fast Response Times:** Cached data loading ensures quick command responses across all features.

### 📊 Logging & Monitoring
- **Rich Logging:** Emoji-based, color-highlighted logs for all major actions.
- **Startup Overview:** Lists all loaded cogs and available commands.
- **Comprehensive Monitoring:** Tracks bot performance and user interactions.

---

## 🛠️ Setup (Personal Use Only)

# ⚠️ **STRICTLY RESTRICTED: PERSONAL USE ONLY**

**This bot was developed specifically for The Chillventory and is NOT intended for public deployment. Any redistribution, forking, or commercial use is prohibited.**

*(Dieser Bot wurde speziell für The Chillventory entwickelt und ist NICHT für die öffentliche Bereitstellung gedacht. Jegliche Weiterverbreitung, Forking oder kommerzielle Nutzung ist untersagt.)*

**If you for any reason want to create a copy for your personal use (which is not recommended), please note:**

This bot is tailored for The Chillventory and not intended for public deployment. If you fork for personal use:

### Prerequisites
- **Python 3.8+** - The bot requires Python 3.8 or higher
- **Discord Bot Token** - Create a bot at [Discord Developer Portal](https://discord.com/developers/applications)
- **External Services** - Various API keys for Rocket League stats, email, etc.

### Quick Setup

1. **Clone the Repository**
   ```bash
   git clone https://github.com/inventory69/HazeWorldBot.git
   cd HazeWorldBot
   ```

2. **Create Virtual Environment (Recommended)**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Configuration**
   - Copy the example environment file:
     ```bash
     cp .env.example .env
     ```
   - Edit `.env` with your configuration:
     ```env
     # Discord Configuration
     DISCORD_BOT_TOKEN=your_bot_token_here
     DISCORD_GUILD_ID=your_guild_id_here

     # Rocket League API (Required for RL features)
     ROCKET_API_BASE=https://api.rocketleague.com
     ROCKET_API_KEY=your_rocket_api_key
     FLARESOLVERR_URL=http://localhost:8191  # For bypassing anti-bot measures

     # Email Configuration (Required for ticket transcripts)
     SMTP_SERVER=smtp.gmail.com
     SMTP_PORT=587
     SMTP_USER=your_email@gmail.com
     SMTP_PASS=your_app_password
     SUPPORT_EMAIL=support@yourdomain.com

     # OpenAI API (Required for changelog generation)
     OPENAI_API_KEY=your_openai_api_key
     ```

5. **Configure Bot Settings**
   - Update role and channel IDs in `Config.py` to match your Discord server
   - Modify permissions and command access as needed

6. **Run the Bot**
   ```bash
   python Main.py
   ```

### Development Setup

For contributors and developers:

1. **Install Development Dependencies**
   ```bash
   pip install ruff  # Code linting and formatting
   ```

2. **Code Quality**
   ```bash
   # Run linting and formatting
   ruff check .
   ruff format .

   # Auto-fix issues
   ruff check --fix .
   ```

3. **Project Structure**
   ```
   HazeWorldBot/
   ├── Cogs/                 # Discord bot cogs (features)
   │   ├── Changelog.py      # Changelog generation
   │   ├── Leaderboard.py    # Leaderboards and activity tracking
   │   ├── ModPerks.py       # Moderation tools
   │   ├── Preferences.py    # User preferences
   │   ├── Profile.py        # User profiles
   │   ├── RocketLeague.py   # RL stats integration
   │   ├── RoleInfo.py       # Role information
   │   ├── TicketSystem.py   # Support ticket system
   │   └── Welcome.py        # Welcome system
   ├── Utils/                # Utility modules
   │   ├── CacheUtils.py     # Caching system
   │   ├── EmbedUtils.py     # Embed formatting
   │   ├── Env.py           # Environment validation
   │   └── Logger.py        # Logging utilities
   ├── Data/                # Persistent data storage
   ├── Logs/                # Log files
   ├── Config.py            # Bot configuration
   ├── Main.py              # Bot entry point
   └── requirements.txt     # Python dependencies
   ```

---

## 📖 Usage Guide

### For Server Members (Lootlings)
```bash
# Get help with available commands
/help

# Check bot status and latency
/status

# View your profile
/profile
/profile @username  # View another user's profile

# Rocket League features
/rlstats platform username  # Get RL stats
/setrlaccount platform username  # Link your RL account

# Preferences and settings
/preferences  # Toggle changelog notifications

# View leaderboards
/leaderboard messages  # Most active members
/leaderboard images    # Most images posted
/leaderboard rl_overall  # Highest RL ranks

# Create support tickets
/ticket  # Start ticket creation process
```

### For Moderators (Slot Keepers)
```bash
# Moderation commands
/modpanel  # Open moderation panel
/modoverview  # View moderation statistics
/moddetails @user  # View user's moderation history
/clear 5  # Clear 5 messages

# Ticket management
# Use interactive buttons in ticket channels:
# - Claim: Claim a ticket
# - Close: Close a ticket
# - Assign: Assign ticket to another mod
```

### For Administrators
```bash
# All moderator commands plus:
!say Hello everyone!  # Send message as bot
!changelog  # Create changelog from recent changes
!optins  # View changelog opt-in statistics
```

### Command Reference

| Command | Description | Access Level |
|---------|-------------|--------------|
| `/help` | Show available commands | All |
| `/status` | Bot status and latency | All |
| `/profile` | User profile information | All |
| `/rlstats` | Rocket League statistics | All |
| `/setrlaccount` | Link RL account | All |
| `/preferences` | User preferences | All |
| `/leaderboard` | View leaderboards | All |
| `/ticket` | Create support ticket | All |
| `/roleinfo` | Role information | All |
| `/modpanel` | Moderation panel | Mods+ |
| `/modoverview` | Moderation statistics | Mods+ |
| `/moddetails` | User moderation history | Mods+ |
| `/clear` | Clear messages | Mods+ |
| `/say` | Send message as bot | Admins |
| `/optins` | View opt-in statistics | Admins |

---

## ⚙️ Configuration

### Environment Variables
The bot uses environment variables for sensitive configuration. All required variables are validated on startup.

### Role Configuration
Update these IDs in `Config.py` to match your Discord server:
- `ADMIN_ROLE_ID`: Administrators with full access
- `MODERATOR_ROLE_ID`: Moderators (Slot Keepers)
- `NORMAL_ROLE_ID`: Regular members (Lootlings)
- `CHANGELOG_ROLE_ID`: Changelog notification role

### Channel Configuration
- `TICKETS_CATEGORY_ID`: Category for support tickets
- `WELCOME_RULES_CHANNEL_ID`: Channel for rules acceptance
- `WELCOME_PUBLIC_CHANNEL_ID`: Channel for welcome messages

### Performance Tuning
The bot includes advanced caching to optimize performance:
- **Activity Data**: Cached for 30 seconds
- **Moderation Data**: Cached for 30 seconds
- **Ticket Data**: Cached for 30 seconds
- **RL API Responses**: Cached for 1 hour

---

## 📋 Requirements & Dependencies

### Core Dependencies
- **discord.py** - Discord API wrapper
- **python-dotenv** - Environment variable management
- **aiohttp** - Asynchronous HTTP client
- **requests** - Synchronous HTTP requests
- **beautifulsoup4** - HTML parsing for web scraping
- **openai** - OpenAI API for changelog generation

### Development Dependencies
- **ruff** - Fast Python linter and formatter
- **rich** - Enhanced console output

### System Requirements
- Python 3.8+
- 100MB RAM minimum
- Stable internet connection
- Discord bot token with appropriate permissions

---

## 🚀 Deployment

### Local Development
```bash
# Run in development mode
python Main.py
```

### Production Deployment
Consider using:
- **Docker** - Containerized deployment
- **PM2** - Process management
- **Systemd** - Service management on Linux
- **Railway** or **Heroku** - Cloud hosting

### Docker Support
The project includes Docker configuration for easy deployment:
```bash
docker build -t hazeworldbot .
docker run -d --env-file .env hazeworldbot
```

---

## 🤝 Contributing

# ⚠️ **NO CONTRIBUTIONS WELCOME**

**Due to the nature of this project as a personal tool, external contributions are not welcome. This repository serves only for personal documentation and archiving.**

*(Aufgrund der Natur dieses Projekts als persönliches Werkzeug sind externe Beiträge nicht erwünscht. Dieses Repository dient nur der persönlichen Dokumentation und Archivierung.)*

*If you for any reason want to use the code, do so at your own risk and without any support.*

---

## 📄 License

**This project is licensed for personal use only and is not intended for redistribution.**

*(Dieses Projekt ist für den persönlichen Gebrauch lizenziert und nicht für die Weiterverbreitung gedacht.)*

This project is licensed for personal use only and is not intended for redistribution - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Personal Project** - This is a personal tool, not intended for the public
- Built with 💖 for The Chillventory community
- Special thanks to contributors and testers
- Powered by discord.py and various open-source libraries

---

# ⚠️ **FINAL WARNING**

**This project is and remains a personal tool. Any use outside the personal context is not authorized and will not be supported.**

*(Dieses Projekt ist und bleibt ein persönliches Werkzeug. Jegliche Nutzung außerhalb des persönlichen Kontexts ist nicht autorisiert und wird nicht unterstützt.)*

**Questions?** Reach out personally or create an issue! 🌿

*Made with 💖 for The Chillventory community - Personal Use Only*