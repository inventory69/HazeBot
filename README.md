# HazeWorldBot 🌿

A Discord bot designed for The Chillventory server ("Haze" on Discord). Built with Python and discord.py, HazeWorldBot enhances moderation, onboarding, changelogs, and community engagement with a modular, inventory-themed experience.

**Note:** This is a personal project. Feel free to fork and adapt it for your own server!

---

## ✨ Features

### 🛠️ Utility & Moderation
- **Prefix & Slash Commands:** Both `!` and `/` commands for all major features.
- **Help System:** `/help` and `!help` show all commands, with mod/admin commands only visible to authorized users.
- **Status:** `/status` and `!status` display bot latency and server count.
- **Message Management:** `!clear` for admins and Slot Keepers (mods) to purge messages.
- **Say Command:** `!say` lets admins send bot messages with embeds and interactive buttons via JSON.
- **Mod Command:** `/mod` and `!mod` for various moderation actions and controls (admin-only).
- **Mod Panel:** `/modpanel` and `!modpanel` for Slot Keepers and Admins to select users and perform moderation actions (Mute, Kick, Ban, Warn with optional reason), lock channels, and set slowmode. Dynamic button states reflect current channel conditions (locked/unlocked, slowmode enabled/disabled). Warnings are tracked per user and stored in `Data/mod_data.json`.
- **Mod Details:** `/moddetails` and `!moddetails` for Slot Keepers and Admins to view detailed moderation history for specific users.
- **Centralized Command Lists:** All admin/mod commands are managed in `Config.py` for consistency.

### 🎫 Ticket System
- **Create Tickets:** `/ticket` and `!ticket` for support, bugs, or applications.
- **Interactive Controls:** Claim, assign, close, delete, and reopen tickets with buttons.
- **Optional Close Messages:** When closing tickets, moderators can include an optional message for the ticket creator.
- **Automatic Archiving:** Tickets are archived immediately after closing to prevent further writing until reopened.
- **Role-Based Permissions:** Slot Keepers (mods) and Admins can claim/close/reopen; only Admins can assign and delete.
- **Transcript & Email:** Closed tickets generate transcripts (including close messages) and can send via email.
- **Automatic Cleanup:** Old closed tickets are deleted after 7 days.
- **Persistent Views:** All ticket buttons remain functional across bot restarts.

### 🚀 Rocket League Integration
- **Stats Fetching:** `/rlstats` and `!rlstats` show player stats for 1v1, 2v2, 3v3, 4v4.
- **Account Linking:** `/setrlaccount` and `!setrlaccount` to save your RL account.
- **Rank Promotion Notifications:** Automatic notifications and congratulation embeds for rank-ups.
- **Performance Caching:** API calls are cached for 1 hour to reduce external requests and improve response times.

### 📝 Changelog System
- **Automated Changelog Generation:** `!changelog` (admin-only) uses GPT-4 Turbo to format PR/commit text as Discord embeds.
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

### 📋 To-Do List System
- **Manage Tasks:** `/todo-update` and `!todo-update` for admins/mods to add, remove, and clear tasks.
- **Multi-Delete:** Select up to 25 tasks at once for batch deletion with confirmation.
- **AI Formatting:** OpenAI GPT-4 Turbo automatically formats tasks with emojis and descriptions.
- **View Tasks:** `/todo-show` and `!todo-show` display the current to-do list.
- **Priority Levels:** Tasks organized by priority (🔴 High, 🟡 Medium, 🟢 Low).
- **Author Tracking:** Each task shows who added it.
- **Channel Restriction:** Management commands restricted to designated todo channel.

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

## 🛠️ Setup

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
!say Hello everyone!  # Send plain message as bot
!say --embed Welcome to the server!  # Send simple embed
!say --json {"embed": {"title": "Announcement"}, "buttons": [{"label": "Click", "style": "primary"}]}  # Embed with buttons
!changelog text:"Your PR text here"  # Create changelog from changes
!mod  # Moderation actions and controls
!optins  # View changelog opt-in statistics
```

### Command Reference

#### User Commands (All Members)

| Command | Prefix | Description |
|---------|--------|-------------|
| `/help` | `!help` | Show available commands |
| `/status` | `!status` | Bot status and latency |
| `/profile` | `!profile` | User profile information |
| `/rlstats [platform] [username]` | `!rlstats` | Rocket League statistics |
| `/setrlaccount [platform] [username]` | `!setrlaccount` | Link RL account |
| `/preferences` | `!preferences` | Toggle changelog notifications |
| `/leaderboard [category]` | `!leaderboard` | View leaderboards by category |
| `/ticket` | `!ticket` | Create support ticket |
| `/roleinfo [role]` | `!roleinfo` | Role information and permissions |
| `/todo-show` | `!todo-show` | Display current to-do list |

#### Moderator Commands (Slot Keepers+)

| Command | Prefix | Description |
|---------|--------|-------------|
| `/clear [amount]` | `!clear` | Delete messages in bulk |
| `/modpanel` | `!modpanel` | Moderation control panel |
| `/modoverview` | `!modoverview` | Moderation statistics |
| `/moddetails [@user]` | `!moddetails` | User moderation history |
| `/todo-update` | `!todo-update` | Create/update to-do items with AI formatting |

#### Administrator Commands (Admins Only)

| Command | Prefix | Description |
|---------|--------|-------------|
| `/changelog` | `!changelog` | Generate and post bot changelogs with AI |
| `/say [message]` | `!say` | Send message as bot with embeds and buttons (JSON support) |
| `/mod [action]` | `!mod` | Moderation actions and controls |
| `/optins` | `!optins` | View opt-in statistics |

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

**Want to help improve HazeWorldBot?** Contributions are welcome!

Please see our [**CONTRIBUTING.md**](CONTRIBUTING.md) for detailed guidelines on how to contribute.

### How to Contribute

1. **Fork the Repository**
   ```bash
   git clone https://github.com/inventory69/HazeWorldBot.git
   cd HazeWorldBot
   ```

2. **Create a Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make Your Changes**
   - Follow the existing code style and patterns
   - Add comments for complex logic
   - Test thoroughly before submitting

4. **Commit with Clear Messages**
   ```bash
   git commit -m "feat: describe your changes"
   ```

5. **Push and Open a Pull Request**
   ```bash
   git push origin feature/your-feature-name
   ```

### Contribution Guidelines

- **Code Style:** Use `ruff` for formatting (run `ruff format .`)
- **Testing:** Ensure all changes are tested in a development environment
- **Documentation:** Update README and code comments as needed
- **Respect Existing Structure:** Follow the modular Cog architecture
- **Async/Await:** Use async patterns throughout (no blocking calls)
- **Error Handling:** Include proper error handling and logging
- **Discord API:** Use discord.py best practices and patterns

### Areas for Contribution

- **Bug Fixes:** Found a bug? We'd love your fix!
- **New Features:** Have an idea? Open an issue first to discuss
- **Documentation:** Help improve README, docstrings, and comments
- **Performance:** Optimize existing code and caching systems
- **Testing:** Add unit tests and improve test coverage

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

You're free to fork, modify, and use this project for your own Discord server!

---

## 🙏 Acknowledgments

- Built with 💖 for The Chillventory community
- Powered by [discord.py](https://github.com/Rapptz/discord.py)
- AI features powered by [OpenAI GPT-4](https://openai.com/)
- Special thanks to all contributors and community members
- Thanks to the open-source libraries that make this project possible

---

**Questions?** Feel free to open an issue or reach out! 🌿

*Made with 💖 for The Chillventory community*