# HazeBot 🌿

A Discord bot designed for The Chillventory server ("Haze" on Discord). Built with Python and discord.py, HazeBot enhances moderation, onboarding, changelogs, and community engagement with a modular, inventory-themed experience.

**Note:** This is a personal project. Feel free to fork and adapt it for your own server!

---

## ℹ️ Special Architecture Notes

- **Test & Production Mode:** The bot automatically detects via the `PROD_MODE` environment variable whether it is running in test or production mode. IDs and tokens are dynamically loaded from `.env` and managed in `Config.py`, allowing safe operation in multiple environments.
- **Rich Logging:** All logs are output with colored emojis and highlights using the `rich` framework (`Utils/Logger.py`). This makes debugging and monitoring in the terminal much easier.
- **Caching Strategies:** The bot uses both in-memory and file-based caching (`Utils/CacheUtils.py`). Frequently used data (e.g., activity, moderation data, API responses) is cached with a configurable TTL to optimize performance and avoid rate limits.
- **AI Features:** For changelog and to-do formatting, the bot uses OpenAI GPT-4.1-Nano models.

---

## ✨ Features

### 🛠️ Utility & Moderation
- **Prefix & Slash Commands:** Both `!` and `/` commands for all major features.
- **Help System:** `/help` and `!help` show all commands, with mod/admin commands only visible to authorized users.
- **Status:** `/status` and `!status` display bot latency and server count.
- **Message Management:** `!clear` for admins and Slot Keepers (mods) to purge messages.
- **Say Command:** `!say` lets admins send bot messages (with embed option).
- **Mod Command:** `/mod` and `!mod` for various moderation actions and controls (mod/admin).
- **Mod Panel:** `/modpanel` and `!modpanel` for Slot Keepers and Admins to select users and perform moderation actions (Mute, Kick, Ban, Warn with optional reason), lock channels, and set slowmode. Dynamic button states reflect current channel conditions (locked/unlocked, slowmode enabled/disabled). Warnings are tracked per user and stored in `Data/mod_data.json`.
- **Mod Overview:** `/modoverview` and `!modoverview` for Slot Keepers and Admins to view moderation statistics and overview.
- **Mod Details:** `/moddetails` and `!moddetails` for Slot Keepers and Admins to view detailed moderation history for specific users.
- **Opt-ins Statistics:** `/optins` and `!optins` for Slot Keepers and Admins to view changelog notification opt-in statistics.
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
- **Persistent Support Buttons:** `!create-button` (admin-only) creates dynamic persistent buttons for any command type (ticket, slash commands, prefix commands).

### 🚀 Rocket League Integration
- **Stats Fetching:** `/rlstats` and `!rlstats` show player stats for 1v1, 2v2, 3v3, 4v4.
- **Account Linking:** `/setrlaccount` and `!setrlaccount` to save your RL account.
- **Account Unlinking:** `/unlinkrlaccount` to remove your linked RL account.
- **Admin Stats:** `/adminrlstats` (admin-only) bypasses cache for immediate stats.
- **Rank Promotion Notifications:** Automatic notifications and congratulation embeds for rank-ups.
- **Persistent Congrats Buttons:** Community can congratulate players on rank-ups (3.5 day timeout, survives bot restarts).
- **Performance Caching:** API calls are cached for 1 hour to reduce external requests and improve response times.

### 📝 Changelog System
- **Automated Changelog Generation:** `!changelog` (admin-only) uses GPT-4.1-Nano to format PR/commit text as Discord embeds.
- **Post to Channel Button:** Instantly post changelogs to the designated channel with a notification.
- **Role Mention:** Changelog notification role can be toggled by users in preferences.

### 📦 Role Info
- **Role Descriptions:** `/roleinfo` and `!roleinfo` show readable info, permissions, and usage tips for Admin, Slot Keeper (mod), and Lootling (member) roles.
- **Autocomplete:** Only main roles selectable in slash command.
- **Command List:** Shows relevant commands for each role.

### 🛠️ Preferences System
- **Changelog Notification Opt-In:** `/preferences` and `!preferences` let users toggle the changelog notification role.

### 👤 Profile System
- **User Profiles:** `/profile` and `!profile` display user avatar, join date, roles, highest RL rank, warnings, resolved tickets, changelog opt-in, and activity stats (messages/images/memes requested/memes generated).
- **Activity Tracking:** Automatically tracks message and image posting activity.
- **Meme Statistics:** Shows both memes requested and custom memes generated.

### 🏆 Leaderboard System
- **Various Leaderboards:** `/leaderboard` and `!leaderboard` with categories for RL ranks (overall/1v1/2v2/3v3/4v4), resolved tickets, most messages, most images posted, memes requested, and memes generated.
- **Real-time Updates:** Activity data is cached for 30 seconds for optimal performance.

### 🎮 Warframe Integration (Beta)
- **Interactive Hub:** `/warframe` opens persistent hub with quick-access buttons for status and market features.
- **Game Status Tracking:** Real-time alerts, fissures, sortie, and invasions via tenno.tools API.
- **Market Search:** Smart item search with fuzzy matching across 3600+ tradeable items.
- **Price Statistics:** Live price data (48h/90d averages, volume, median) from warframe.market v2 API.
- **Order Listings:** View top buy/sell orders with online status indicators (🟢 Ingame/Online, ⚫ Offline).
- **Trade Message Generator:** Copy-paste ready in-game chat messages in warframe.market format.
- **Interactive UI:** Ephemeral responses, modal search, dropdown selections, and refresh buttons.
- **Smart Caching:** Status (60s), stats (10min), items (1h) for optimal performance.

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
- **AI Formatting:** OpenAI GPT-4.1-Nano automatically formats tasks with emojis and descriptions.
- **Priority Levels:** Tasks organized by priority (🔴 High, 🟡 Medium, 🟢 Low).
- **Author Tracking:** Each task shows who added it.
- **Channel Restriction:** Management commands restricted to designated todo channel.

### 🎭 Daily Meme System
- **Daily Memes:** Automatically posts a trending meme every day at 12:00 PM.
- **Multi-Platform Sources:** Supports both Reddit and Lemmy for meme fetching.
  - **Reddit:** Standard subreddit format (e.g., `memes`, `dankmemes`)
  - **Lemmy:** Instance@community format (e.g., `lemmy.world@memes`)
- **Quality Curation:** Sources from configurable source list (default: 10 curated sources).
- **Smart Selection:** Picks from top upvoted/scored memes for quality content.
- **NSFW Support:** Includes NSFW memes with proper warnings if funny.
- **Interactive Meme Hub:** `/meme` opens interactive hub with buttons for Reddit, Lemmy, or random memes.
- **Direct Source Selection:** `/meme memes` or `!meme memes` to get memes from specific sources.
- **Autocomplete:** Slash command includes autocomplete for all configured sources.
- **Requester Attribution:** All meme requests show who requested the meme (for all users).
- **Score Display:** Shows upvotes/score, source, and author for both platforms.
- **Role Notification:** Mentions meme notification role for daily posts.
- **Cooldown System:** 10-second cooldown between requests for non-admin/mod users.
- **Admin Management:** Full source list management commands.
  - `!memesubreddits` - List current meme sources (Reddit & Lemmy)
  - `!addsubreddit <name>` - Add a Reddit subreddit or Lemmy community
  - `!removesubreddit <name>` - Remove a source
  - `!resetsubreddits` - Reset to defaults
  - `!lemmycommunities` - List Lemmy communities
  - `!addlemmy <instance@community>` - Add Lemmy community
  - `!removelemmy <instance@community>` - Remove Lemmy community
  - `!resetlemmy` - Reset Lemmy communities
  - `!memesources` - List enabled/disabled sources
  - `!enablesource <reddit|lemmy>` - Enable a source
  - `!disablesource <reddit|lemmy>` - Disable a source
  - `!resetsources` - Reset source settings
  - `!dailyconfig` - Configure daily meme posting
- **Test Commands:** `!testmeme` (Reddit) for testing.
- **Persistent Configuration:** Source list saved to file across restarts.

### 🎨 Custom Meme Generator (Imgflip Integration)
- **100+ Templates:** Access to 100+ popular meme templates from Imgflip.
- **Interactive Template Browser:** Browse templates with live preview and button selection.
- **Dynamic Text Fields:** Automatically adapts to template requirements (2-5 text boxes).
- **Template Caching:** 24-hour cache with automatic refresh for optimal performance.
- **Smart Preview System:** Generate and preview memes before posting.
- **Channel Routing:** Post memes to specific channels (integrated with Server Guide).
- **Usage Tracking:** Track generated memes in user profiles and leaderboards.
- **Multi-Box Support:** Full support for templates with 3+ text boxes using Imgflip's boxes[] API.
- **Commands:**
  - `/creatememe` - Interactive meme generator with template selection
  - `!refreshtemplates` (admin) - Refresh template cache from Imgflip API

### 🛠️ Enhanced Bot Management
- **Interactive Cog Management:** `!load`, `!unload`, and `!reload` without arguments open interactive dropdowns.
  - `!load` - Shows all unloaded cogs with file name → class name mapping
  - `!unload` - Shows all loaded cogs (except CogManager)
  - `!reload` - Shows all loaded cogs (except CogManager)
- **Smart Name Resolution:** Automatically converts between file names and class names (e.g., `Changelog.py` ↔ `ChangelogCog`).
- **Cog-Specific Logs:** `!logs` / `!viewlogs` / `!coglogs` view logs for specific cogs with statistics.
- **URL Censoring:** Automatic redaction of sensitive URLs and credentials in log viewer.
- **Extension Validation:** Proper error handling for unloaded or invalid cogs.
- **Persistent Views:** Interactive dropdowns remain functional for 5 minutes.
- **File Logging:** All logs saved to `Logs/HazeBot.log` with UTF-8 encoding.
- **Log Statistics:** View INFO, WARNING, ERROR, and DEBUG counts per cog.
- **Slash Command Sync:** `!sync` (admin) to manually sync slash commands to guild.

### ⚡ Performance & Caching
- **Advanced Caching System:** Custom-built caching utilities with in-memory and file-based caching for optimal performance.
- **Optimized Data Loading:** All data operations use async caching with configurable TTL to reduce I/O operations.
- **Reduced API Calls:** External API requests are intelligently cached to minimize rate limiting and improve response times.
- **Fast Response Times:** Cached data loading ensures quick command responses across all features.

### 📊 Logging & Monitoring
- **Rich Logging:** Emoji-based, color-highlighted logs for all major actions.
- **Discord Logging:** Real-time log streaming to Discord channel (all levels: DEBUG, INFO, WARNING, ERROR, CRITICAL).
- **Live Log Channel:** Automatically posts all bot logs with ANSI formatting and cog-specific emojis.
- **Toggle Control:** `!togglediscordlogs` to enable/disable Discord logging (Admin only).
- **Test Command:** `!testdiscordlog` to test logging with sample messages.
- **Batching System:** Logs are sent in batches every 5 seconds to avoid rate limits.
- **Startup Overview:** Lists all loaded cogs and available commands.
- **Comprehensive Monitoring:** Tracks bot performance and user interactions.

---

## 🛠️ Setup

### Prerequisites
- **Python 3.9+** - The bot requires Python 3.9 or higher
- **Discord Bot Token** - Create a bot at [Discord Developer Portal](https://discord.com/developers/applications)
- **External Services** - Various API keys for Rocket League stats, email, etc.

### Quick Setup

1. **Clone the Repository**
   ```bash
   git clone https://github.com/inventory69/HazeBot.git
   cd HazeBot
   ```

2. **Create Virtual Environment (Recommended)**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   # For fish shell: source .venv/bin/activate.fish
   # For PowerShell: .venv\Scripts\Activate.ps1
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

     # Imgflip API (Required for meme generator)
     IMGFLIP_USERNAME=your_imgflip_username
     IMGFLIP_PASSWORD=your_imgflip_password

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
   HazeBot/
   ├── Cogs/                 # Discord bot cogs (features)
   │   ├── Changelog.py      # Changelog generation with AI
   │   ├── CogManager.py     # Dynamic cog loading/unloading with interactive views
   │   ├── DailyMeme.py      # Daily meme system with Reddit/Lemmy integration
   │   ├── DiscordLogging.py # Real-time log streaming to Discord
   │   ├── Leaderboard.py    # Leaderboards and activity tracking
   │   ├── MemeGenerator.py  # Custom meme generator with Imgflip API (100+ templates)
   │   ├── ModPerks.py       # Moderation tools and panels
   │   ├── Preferences.py    # User preferences
   │   ├── Presence.py       # Dynamic presence updates
   │   ├── Profile.py        # User profiles with activity stats
   │   ├── RocketLeague.py   # RL stats integration with persistent congrats views
   │   ├── RoleInfo.py       # Role information
   │   ├── ServerGuide.py    # Interactive server guide
   │   ├── SupportButtons.py # Persistent support buttons
   │   ├── TicketSystem.py   # Support ticket system
   │   ├── TodoList.py       # To-do list management with AI
   │   ├── Utility.py        # Utility commands and help system
   │   ├── Warframe.py       # Warframe market and status integration (Beta)
   │   ├── Welcome.py        # Welcome system with interactive rules
   │   ├── _DailyMemeViews.py # Meme hub views and buttons
   │   └── __init__.py       # Cog initialization
   ├── Utils/                # Utility modules
   │   ├── CacheUtils.py     # Advanced caching system
   │   ├── EmbedUtils.py     # Embed formatting utilities
   │   ├── Env.py            # Environment validation
   │   └── Logger.py         # Rich logging with file output
   ├── Data/                 # Data storage directory
   │   └── TestData/         # Test data (for PROD_MODE=false)
   ├── Cache/                # Cache files for API responses
   ├── Logs/                 # Log files (HazeBot.log)
   ├── Config.py             # Bot configuration and constants
   ├── Main.py               # Bot entry point
   ├── pyproject.toml        # Project configuration
   ├── requirements.txt      # Python dependencies
   └── .env.example          # Environment variables template
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

# Get memes
/meme  # Open interactive Meme Hub
/meme memes  # Get meme from r/memes directly
/meme lemmy.world@memes  # Get meme from Lemmy

# Create custom memes
/creatememe  # Open interactive meme generator with 100+ templates

# Preferences and settings
/preferences  # Toggle changelog notifications

# Role information
/roleinfo Admin  # View Admin role info
/roleinfo "Slot Keeper"  # View Moderator role info

# View leaderboards
/leaderboard messages  # Most active members
/leaderboard images    # Most images posted
/leaderboard rl_overall  # Highest RL ranks

# Create support tickets
/ticket  # Start ticket creation process

# Rocket League features
/rlstats platform username  # Get RL stats
/setrlaccount platform username  # Link your RL account
/unlinkrlaccount  # Unlink your RL account
/rocket  # Open interactive RL Hub

# Warframe features (Beta)
/warframe  # Open interactive Warframe Hub
/warframemarket Ash Prime Set  # Search Warframe market
```

### For Moderators (Slot Keepers)
```bash
# Moderation commands
/mod  # Moderation actions and controls
/modpanel  # Open moderation panel with interactive buttons
/modoverview  # View moderation statistics
/moddetails @user  # View user's moderation history
!clear 5  # Clear 5 messages (prefix only)
/optins  # View changelog opt-in statistics
!adminrlstats platform username  # Admin RL stats - bypass cache (prefix only)

# To-Do management
/todo-update  # Manage server to-do list with AI formatting

# Ticket management
# Use interactive buttons in ticket channels:
# - Claim: Claim a ticket
# - Close: Close a ticket with optional message
# - Assign: Assign ticket to another mod
# - Reopen: Reopen a closed ticket
```

### For Administrators
```bash
# All moderator commands plus:
!say Hello everyone!  # Send message as bot
!say --embed Your message here  # Send as simple embed
!say --json {...}  # Send with full JSON control
!say --builder  # Interactive embed builder

# Changelog management
!changelog  # Create and post changelog with AI formatting
!changelog --text "Your PR text here"  # Generate changelog from text

# Discord logging
!togglediscordlogs  # Toggle Discord logging on/off
!testdiscordlog  # Send test logs to Discord channel

# Bot management
!create-button  # Create persistent support buttons
!server-guide  # Send interactive server guide
!restorecongratsview message_id user_id  # Restore congrats button

# Cog management
!load CogName  # Load a cog
!unload CogName  # Unload a cog
!reload  # Interactive cog selector (or !reload CogName for direct reload)
!listcogs  # List all cogs and their status
!logs  # Interactive log viewer (or !logs CogName for specific cog)
!sync  # Sync slash commands to guild

# Meme management
!memesubreddits  # List current meme sources (Reddit & Lemmy)
!addsubreddit funny  # Add a Reddit subreddit
!addsubreddit lemmy.world@memes  # Add a Lemmy community
!removesubreddit funny  # Remove a source
!resetsubreddits  # Reset to default sources
!lemmycommunities  # List Lemmy communities
!addlemmy lemmy.world@memes  # Add Lemmy community
!removelemmy lemmy.world@memes  # Remove Lemmy community
!resetlemmy  # Reset Lemmy communities
!memesources  # List enabled/disabled sources
!enablesource reddit  # Enable a source
!disablesource lemmy  # Disable a source
!resetsources  # Reset source settings
!dailyconfig  # Configure daily meme posting
!testmeme  # Test Reddit meme fetching
!refreshtemplates  # Refresh meme templates from Imgflip API
```

### Command Reference

#### User Commands (All Members)

| Command | Prefix | Description |
|---------|--------|-------------|
| `/help` | `!help` | Show available commands |
| `/status` | `!status` | Bot status and latency |
| `/profile [@user]` | `!profile` | User profile information |
| `/preferences` | `!preferences` | Toggle changelog notifications |
| `/roleinfo [role]` | `!roleinfo` | Role information and permissions |
| `/leaderboard [category]` | `!leaderboard` | View leaderboards by category |
| `/ticket` | `!ticket` | Create support ticket |
| `/meme [source]` | `!meme` | Get memes from specific source or open interactive hub |
| `/creatememe` | - | Create custom memes with Imgflip templates (slash only) |
| `/rlstats [platform] [username]` | `!rlstats` | Rocket League statistics |
| `/setrlaccount [platform] [username]` | `!setrlaccount` | Link RL account |
| `/unlinkrlaccount` | `!unlinkrlaccount` | Unlink RL account |
| `/rocket` | `!rocket` | Rocket League Hub |
| `/warframe` | `!warframe` | Warframe hub with market and status (Beta) |
| `/warframemarket [item]` | `!warframemarket` | Search Warframe market items (Beta) |

#### Moderator Commands (Slot Keepers+)

| Command | Prefix | Description |
|---------|--------|-------------|
| `!clear [amount]` | - | Delete messages in bulk (prefix only) |
| `/mod` | `!mod` | Moderation actions and controls |
| `/modpanel` | `!modpanel` | Moderation control panel |
| `/modoverview` | `!modoverview` | Moderation statistics |
| `/moddetails [@user]` | `!moddetails` | User moderation history |
| `/optins` | `!optins` | View changelog opt-in statistics |
| `/todo-update` | `!todo-update` | Create/update to-do items with AI formatting |
| `!adminrlstats [platform] [username]` | - | Admin RL stats - bypass cache (prefix only) |

#### Administrator Commands (Admins Only)

| Command | Prefix | Description |
|---------|--------|-------------|
| `!changelog [--text]` | - | Generate and post bot changelogs with AI (prefix only) |
| `!say [message]` | - | Send message as bot (prefix only) |
| `!testmeme` | - | Test daily meme function with Reddit (prefix only) |
| `!memesubreddits` | - | List current meme sources (Reddit & Lemmy) (prefix only) |
| `!addsubreddit [name]` | - | Add a Reddit subreddit or Lemmy community (format: instance@community) (prefix only) |
| `!removesubreddit [name]` | - | Remove a meme source (prefix only) |
| `!resetsubreddits` | - | Reset meme sources to defaults (prefix only) |
| `!lemmycommunities` | - | List Lemmy communities (prefix only) |
| `!addlemmy [instance@community]` | - | Add Lemmy community (prefix only) |
| `!removelemmy [instance@community]` | - | Remove Lemmy community (prefix only) |
| `!resetlemmy` | - | Reset Lemmy communities (prefix only) |
| `!memesources` | - | List enabled/disabled sources (prefix only) |
| `!enablesource [source]` | - | Enable a meme source (reddit/lemmy) (prefix only) |
| `!disablesource [source]` | - | Disable a meme source (prefix only) |
| `!resetsources` | - | Reset source settings (prefix only) |
| `!dailyconfig` | - | Configure daily meme posting (prefix only) |
| `!refreshtemplates` | - | Refresh meme templates from Imgflip API (prefix only) |
| `!restorecongratsview [message_id] [user_id]` | - | Restore persistent congrats button (prefix only) |
| `!create-button` | - | Create persistent buttons for any command type (prefix only) |
| `!server-guide` | - | Send interactive server guide with command buttons (prefix only) |
| `!load [cog_name]` | - | Load a cog (interactive if no name) (prefix only) |
| `!unload [cog_name]` | - | Unload a cog (interactive if no name) (prefix only) |
| `!reload [cog_name]` | - | Reload a cog (interactive if no name) (prefix only) |
| `!listcogs` | - | List all available cogs and their status (prefix only) |
| `!logs [cog_name]` | - | View cog-specific logs with statistics (prefix only) |
| `!sync` | - | Sync slash commands to guild (prefix only) |
| `!togglediscordlogs` | - | Toggle Discord logging on/off (prefix only) |
| `!testdiscordlog` | - | Test Discord logging with sample messages (prefix only) |

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
- **difflib** - Fuzzy matching for Warframe item search

### Development Dependencies
- **ruff** - Fast Python linter and formatter
- **rich** - Enhanced console output

### System Requirements
- Python 3.9+
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
- **PM2** - Process management
- **Systemd** - Service management on Linux
- **Railway** or **Heroku** - Cloud hosting

---

## 🤝 Contributing

**Want to help improve HazeBot?** Contributions are welcome!

Please see our [**CONTRIBUTING.md**](CONTRIBUTING.md) for detailed guidelines on how to contribute.

### How to Contribute

1. **Fork the Repository**
   ```bash
   git clone https://github.com/inventory69/HazeBot.git
   cd HazeBot
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
- AI features powered by [OpenAI GPT-4.1-Nano](https://openai.com/)
- Special thanks to all contributors and community members
- Thanks to the open-source libraries that make this project possible

---

**Questions?** Feel free to open an issue or reach out! 🌿

*Made with 💖 for The Chillventory community*