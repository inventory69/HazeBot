# HazeWorldBot 🌿

**Note:** This bot is not intended for public use.
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
- **Mod Overview:** `/modoverview` and `!modoverview` for Slot Keepers and Admins to view top users by moderation actions (warnings, kicks, bans, mutes).
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

### 📝 Changelog System
- **Automated Changelog Generation:** `!generatechangelog` uses GPT-4 Turbo to format PR/commit text as Discord embeds.
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

### 🏆 Leaderboard System
- **Various Leaderboards:** `/leaderboard` and `!leaderboard` with categories for RL ranks (overall/1v1/2v2/3v3/4v4), resolved tickets, most messages, and most images posted.

### 🎮 Dynamic Presence
- **Inventory-Themed Status:** Bot presence updates hourly with fun inventory messages and emojis.

### 🎉 Welcome System
- **Interactive Rule Acceptance:** New members select interests and accept rules via dropdown and button.
- **Polished Welcome Cards:** Personalized welcome embeds with inventory vibes.
- **Persistent Welcome Buttons:** Community can greet new members with themed replies.
- **Automatic Cleanup:** Welcome messages are deleted when members leave.

### 📊 Logging & Monitoring
- **Rich Logging:** Emoji-based, color-highlighted logs for all major actions.
- **Startup Overview:** Lists all loaded cogs and available commands.

---

## 🛠️ Setup (Personal Use Only)

This bot is tailored for The Chillventory and not intended for public deployment. If you fork for personal use:

1. **Clone the Repository**
    ```
    git clone https://github.com/inventory69/HazeWorldBot.git
    cd HazeWorldBot
    ```

2. **Install Dependencies**
    ```
    pip install -r requirements.txt
    ```

3. **Environment Variables**
    - Create a `.env` file with your bot token, guild ID, and required API keys:
      ```
      DISCORD_BOT_TOKEN=your_bot_token_here
      DISCORD_GUILD_ID=your_guild_id_here
      ROCKET_API_BASE=your_rocket_api_base
      ROCKET_API_KEY=your_rocket_api_key
      FLARESOLVERR_URL=your_flaresolverr_url
      SMTP_SERVER=your_smtp_server
      SMTP_PORT=your_smtp_port
      SMTP_USER=your_smtp_user
      SMTP_PASS=your_smtp_pass
      SUPPORT_EMAIL=your_support_email
      ```
    - Update role and channel IDs in the code as needed.

4. **Run the Bot**
    ```
    python Main.py
    ```

---

## 📖 Usage

- **Admins:** Use `!clear`, `!say`, `!generatechangelog`, manage tickets, access mod panel and overview.
- **Slot Keepers (Mods):** Use `!clear`, claim/close tickets, access mod panel and overview, view leaderboards.
- **Members (Lootlings):** Use `/help`, `/status`, `/rlstats`, `/preferences`, `/profile`, `/leaderboard`, enjoy onboarding.
- **Changelog Notifications:** Opt-in via `/preferences` to get notified for bot updates.

---

## 📋 Requirements

- Python 3.8+
- discord.py
- python-dotenv
- aiohttp
- requests
- bs4
- uuid
- rich
- openai

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

Made with 💖 for The Chillventory community.  
Questions? Reach out personally! 🌿