# HazeBot Features - Complete List

Comprehensive documentation of all HazeBot features and commands.

## Table of Contents

- [🎮 Gaming Integration](#-gaming-integration)
- [🎭 Meme System](#-meme-system)
- [🎫 Ticket System](#-ticket-system)
- [🛠️ Moderation Tools](#️-moderation-tools)
- [👤 User Features](#-user-features)
- [📝 Content Management](#-content-management)
- [🛠️ Bot Management](#️-bot-management)
- [⚡ Performance Features](#-performance-features)

---

## 🎮 Gaming Integration

### Rocket League
**Commands:** `/rlstats`, `!rlstats`, `/setrlaccount`, `!setrlaccount`, `/unlinkrlaccount`

- Stats fetching for all competitive modes (1v1, 2v2, 3v3, 4v4)
- Account linking system (save platform + username)
- Admin stats command (bypasses cache)
- Automatic rank promotion notifications with congratulation embeds
- Persistent congratulation buttons (3.5 day timeout, survives bot restarts)
- Performance caching (1 hour TTL)
- Division tracking (e.g., "Diamond III Div 2")
- FlareSolverr integration for Cloudflare bypass

### Warframe (Beta)
**Commands:** `/warframe`

- **Interactive Hub:** Persistent buttons for quick access to all features
- **Game Status:** Real-time alerts, fissures, sortie, invasions (tenno.tools API)
- **Market Search:** Fuzzy matching across 3600+ tradeable items
- **Price Statistics:** 48h/90d averages, volume, median (warframe.market v2 API)
- **Order Listings:** Top buy/sell orders with online status (🟢 Ingame/Online, ⚫ Offline)
- **Trade Messages:** Auto-generated copy-paste chat messages (warframe.market format)
- **Smart Caching:** Status (60s), stats (10min), items (1h)

---

## 🎭 Meme System

### Daily Meme System
**Commands:** `/meme`, `!meme`

**Automated Daily Posts:**
- Configurable schedule (default: daily at specific time)
- Multi-platform support (Reddit + Lemmy)
- Quality curation from top-scored posts
- NSFW support with warnings
- Role notifications (configurable)

**GUI Configuration (Mods/Admins):**
- Enable/disable daily memes
- Schedule time and target channel
- NSFW toggle
- Role mention settings
- Minimum score threshold
- Max sources to fetch from
- Pool size for variety
- Add/remove Reddit subreddits
- Add/remove Lemmy communities (format: `instance@community`)
- Platform enable/disable (Reddit/Lemmy)
- Test function

**Interactive Meme Hub (All Users):**
- Get random memes
- Choose specific sources (with autocomplete)
- Browse and select from configured sources
- Requester attribution on all memes
- Score display (upvotes/score, source, author)
- 10-second cooldown (non-admin/mod)

### Custom Meme Generator
**Commands:** `/creatememe`, `!refreshtemplates` (admin)

- 100+ Imgflip templates
- Interactive template browser with live preview
- Dynamic text fields (2-5 boxes automatically)
- Smart preview system (generate before posting)
- Channel routing (integrated with Server Guide)
- Usage tracking (profiles & leaderboards)
- Multi-box support (Imgflip boxes[] API)
- 24-hour template cache with auto-refresh

---

## 🎫 Ticket System

**Commands:** `/ticket`, `!ticket`, `!create-button` (admin)

**Features:**
- Multiple ticket types (support, bugs, applications)
- Interactive controls with buttons (claim, assign, close, delete, reopen)
- Optional close messages for ticket creators
- Automatic archiving on close (prevents writing until reopened)
- Role-based permissions:
  - Mods & Admins: Claim, close, reopen
  - Admins only: Assign, delete
- Transcript generation (includes close messages)
- Email support for transcripts
- Automatic cleanup (7 days after close)
- Persistent views (buttons work after bot restart)
- Persistent support buttons (create buttons for any command type)

---

## 🛠️ Moderation Tools

### Mod Panel
**Commands:** `/modpanel`, `!modpanel`, `/mod`, `!mod`

**User Actions:**
- Mute, Kick, Ban, Warn (with optional reason)
- Warning tracking (stored in `Data/mod_data.json`)
- User selection dropdown
- Reason input for actions

**Channel Controls:**
- Lock/Unlock channels
- Set slowmode (dynamic button states)
- Current status indicators

**Statistics:**
- `/modoverview`, `!modoverview` - Server-wide mod stats
- `/moddetails`, `!moddetails` - User-specific mod history
- `/optins`, `!optins` - Changelog notification opt-in stats

### Message Management
**Commands:** `!clear` (admin/mod), `!say` (admin)

- Bulk message deletion (admin/mod)
- Send messages as bot (with embed option)

---

## 👤 User Features

### Profile System
**Commands:** `/profile`, `!profile`

**Displays:**
- Discord avatar and user info
- Join date and roles
- Highest Rocket League rank
- Warning count
- Resolved tickets count
- Changelog notification opt-in status
- Activity statistics:
  - Messages sent
  - Images posted
  - Memes requested
  - Custom memes generated

**Activity Tracking:**
- Automatic tracking of all user interactions
- Real-time updates
- Persistent storage

### Leaderboard System
**Commands:** `/leaderboard`, `!leaderboard`

**Categories:**
- Rocket League ranks (overall, 1v1, 2v2, 3v3, 4v4)
- Resolved tickets
- Most messages sent
- Most images posted
- Memes requested
- Memes generated

**Performance:**
- Real-time data
- 30-second cache for optimal response times

### Preferences System
**Commands:** `/preferences`, `!preferences`

- Toggle changelog notification role
- Personal settings management

### Role Info
**Commands:** `/roleinfo`, `!roleinfo`

- Detailed role descriptions (Admin, Mod, Member)
- Permission explanations
- Usage tips
- Command lists per role
- Autocomplete for main roles

---

## 📝 Content Management

### Changelog System
**Commands:** `!changelog` (admin)

- AI-powered formatting (OpenAI GPT-4.1-Nano)
- Convert PR/commit text to Discord embeds
- Post to channel button
- Role mention notification
- User opt-in/opt-out system

### Todo List System
**Commands:** `/todo-update`, `!todo-update` (admin/mod)

- Add, remove, clear tasks
- Multi-delete (up to 25 tasks with confirmation)
- AI formatting (GPT-4.1-Nano adds emojis & descriptions)
- Priority levels: 🔴 High, 🟡 Medium, 🟢 Low
- Author tracking
- Channel restriction (designated todo channel only)

### Welcome System
**Automatic on member join:**

- Interactive rule acceptance
- Interest selection dropdown
- Personalized welcome embeds (inventory-themed)
- Persistent welcome buttons (community greetings)
- Automatic cleanup on member leave

### Dynamic Presence
**Automatic hourly updates:**

- Inventory-themed status messages
- Random emoji selection
- Fun inventory messages

---

## 🛠️ Bot Management

### Cog Management
**Commands:** `!load`, `!unload`, `!reload` (admin)

**Interactive Dropdowns:**
- `!load` - All unloaded cogs with file → class name mapping
- `!unload` - All loaded cogs (except CogManager)
- `!reload` - All loaded cogs (except CogManager)

**Features:**
- Smart name resolution (auto-convert file/class names)
- Extension validation
- Persistent views (5-minute timeout)
- Protection for critical cogs (CogManager cannot be unloaded)

### Logging System
**Commands:** `!logs`, `!viewlogs`, `!coglogs`, `!togglediscordlogs`, `!testdiscordlog`

**Console Logging:**
- Rich framework with colored emojis
- Cog-specific prefixes
- File logging (`Logs/HazeBot.log`)

**Discord Logging:**
- Real-time log streaming to Discord channel
- All levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- ANSI formatting with cog-specific emojis
- Toggle control (admin)
- Batching system (5-second intervals to avoid rate limits)
- Test command for verification

**Cog-Specific Logs:**
- View logs for individual cogs
- Statistics (INFO, WARNING, ERROR, DEBUG counts)
- URL censoring (sensitive data redaction)

### Other Commands
**Commands:** `!sync`, `/help`, `!help`, `/status`, `!status`

- `!sync` - Manually sync slash commands (admin)
- `/help` - Show all commands (role-based visibility)
- `/status` - Bot latency and server count
- Startup overview - Lists loaded cogs and available commands

---

## ⚡ Performance Features

### Advanced Caching System
**Implementation:** `Utils/CacheUtils.py`

- In-memory caching (fast access)
- File-based caching (persistent)
- Configurable TTL per cache type
- Automatic expiration
- Cache hit/miss tracking

**Cached Data:**
- Rocket League stats (1 hour)
- Warframe data (60s - 1h depending on type)
- Meme templates (24 hours)
- Activity data (30 seconds)
- API responses (varies by endpoint)

### Optimized Data Loading
- Async caching for all data operations
- Reduced I/O operations
- Smart TTL management
- External API request minimization
- Fast command response times

### Environment Management
**Variables:** `.env` file

- Test & Production mode (`PROD_MODE`)
- Dynamic ID/token loading
- Safe multi-environment operation
- Separate configs per environment

---

## 📚 Additional Resources

- **[Bot Setup Guide](BOT_SETUP.md)** - Discord bot installation & configuration
- **[Admin Panel Setup](ADMIN_PANEL_SETUP.md)** - Web/mobile interface setup
- **[API Documentation](../api/README.md)** - REST API endpoints
- **[Deployment Guide](DEPLOYMENT_CHECKLIST.md)** - Production deployment
- **[Contributing](CONTRIBUTING.md)** - Development guidelines
