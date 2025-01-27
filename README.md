# Discord Voice Time Tracker Bot

A Discord bot that tracks and manages voice channel activity time for server members. The bot provides features like daily voice time tracking, leaderboards, and automatic daily resets.

## Features

- 🎤 **Voice Time Tracking**: Automatically tracks time spent in voice channels for all users
- 📊 **Daily Leaderboard**: View the top users by voice channel activity
- 🔄 **Daily Reset**: Automatically resets counters daily at 00:10 CET
- 💾 **Backup System**: Creates daily backups of tracking data
- 🛠️ **Admin Commands**: Includes restart and update functionality for bot management

## Prerequisites

- Python 3.8 or higher
- Discord Bot Token
- Required Python packages (listed in requirements.txt)

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/discord-offlinepresence-detector.git
cd discord-offlinepresence-detector
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the root directory (or rename `.env.example` to `.env`) and add your Discord bot token:
```
DISCORD_TOKEN=your_discord_bot_token_here
```

## Usage

To start the bot:
```bash
python bot.py
```

### Commands

- `!leaderboard` - Display the daily voice time leaderboard
- `!restart` - Restart the bot (admin only)

## Configuration

The bot includes several configurable features:

- **Ignored Users**: Configure `IGNORED_USER_IDS` in `bot.py` to exclude specific users from tracking
- **Backup System**: Automatic backups are created before each daily reset

## Technical Details

- Built with discord.py
- Uses JSON for data persistence
- Implements timezone handling with pytz
- Includes comprehensive error handling and logging

## Dependencies

- discord.py >= 2.3.2
- python-dotenv >= 1.0.0
- aiohttp >= 3.8.5
- pytz >= 2023.3

## License

This project is open source and available under the MIT License.
