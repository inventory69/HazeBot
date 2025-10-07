# HazeWorldBot 🌟

A personal Discord bot designed for The Chillventory server, known as Haze in Discord. Built with Python and discord.py, this bot enhances community interactions with welcoming features, utility commands, and a chill vibe. **Note: This is a personal project and not intended for public use or distribution.**

## ✨ Description

HazeWorldBot (Haze) is crafted to make The Chillventory Discord server more engaging and user-friendly. It handles new member onboarding with interactive rule acceptance, role assignments, and fun welcome messages. The bot also provides essential utility commands for moderation and information.

## 🚀 Features

- **Welcome System** 🎉
  - Interactive rule acceptance with role selection
  - Polished welcome cards with inventory-themed messages
  - Persistent welcome buttons for community engagement
  - Automatic cleanup of messages when members leave

- **Utility Commands** 🛠️
  - `/help` and `!help`: Display available commands
  - `/status` and `!status`: Show bot latency and guild count
  - `!clear`: Admin-only message purging
  - `!say`: Admin-only message sending (with embed option)

- **Logging & Monitoring** 📊
  - Custom emoji-based logging for easy tracking
  - Startup command overview for debugging

- **Modular Design** 🔧
  - Cog-based architecture for easy extension
  - Support for both prefix (`!`) and slash (`/`) commands

## 🛠️ Setup (Personal Use Only)

This bot is configured for a specific server and is not set up for general deployment. If you're forking for personal use:

1. **Clone the Repository** 📥
   ```
   git clone https://github.com/inventory69/HazeWorldBot.git
   cd HazeWorldBot
   ```

2. **Install Dependencies** 📦
   ```
   pip install -r requirements.txt
   ```

3. **Environment Variables** 🔐
   - Create a `.env` file with your bot token and guild ID:
     ```
     DISCORD_BOT_TOKEN=your_bot_token_here
     DISCORD_GUILD_ID=your_guild_id_here
     ```
   - Update role and channel IDs in the code as needed.

4. **Run the Bot** ▶️
   ```
   python Main.py
   ```

## 📖 Usage

- **For Admins**: Use `!clear` to manage messages, `!say` to send announcements.
- **For Users**: Interact with welcome flows, use `/help` for command info.
- **Logging**: Check console output for bot activities with custom emojis.

## 📋 Requirements

- Python 3.8+
- discord.py
- python-dotenv

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. (Though it's personal, feel free to adapt!)

---

Made with 💖 for The Chillventory community. If you have questions, reach out personally! 🌿