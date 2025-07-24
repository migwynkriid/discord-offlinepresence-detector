# Discord Offline Presence Detector Bot

A comprehensive Discord bot that tracks voice chat activity, monitors user presence changes, and provides detailed analytics with configurable watchlists and ignore lists.

## 🚀 Features

### Core Functionality
- **Voice Chat Tracking**: Monitors and records time spent in voice channels
- **Presence Detection**: Detects when watched users go offline and sends notifications
- **Leaderboard System**: Displays voice chat time rankings with real-time status
- **Automatic Backups**: Daily backup system with timestamp-based file management
- **Reaction-based Monitoring**: Responds to specific emoji reactions for enhanced interaction

### Management Commands
- **Watchlist Management**: Add/remove users to monitor for offline notifications
- **Ignore List Management**: Exclude specific users from leaderboard tracking
- **Backup System**: Download latest backup files on demand
- **User ID Listing**: Administrative tool to view all tracked users
- **Bot Management**: Restart and update commands for maintenance

## 📋 Commands

### Public Commands
- `!leaderboard` - Display voice chat time rankings (excludes ignored users)

### Administrative Commands (Requires "Manage Server" permission)
- `!watchlist add <user_id>` - Add user to offline monitoring
- `!watchlist remove <user_id>` - Remove user from offline monitoring
- `!watchlist list` - Show all watched users
- `!ignore add <user_id>` - Add user to ignore list (excludes from leaderboard)
- `!ignore remove <user_id>` - Remove user from ignore list
- `!ignore list` - Show all ignored users
- `!listid` - Display all tracked users with IDs and usernames
- `!backup` - Upload the latest backup file
- `!restart` - Restart the bot
- `!update` - Update bot from git repository

## 🛠️ Installation & Setup

### Prerequisites
- Python 3.8 or higher
- Discord Bot Token
- Git (for update functionality)

### Step 1: Clone the Repository
```bash
git clone <repository-url>
cd discord-offlinepresence-detector
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Environment Configuration
1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
2. Edit `.env` and add your Discord bot token:
   ```
   DISCORD_TOKEN=your_discord_bot_token_here
   ```

### Step 4: Discord Bot Setup
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application and bot
3. Copy the bot token to your `.env` file
4. Enable the following bot permissions:
   - Read Messages/View Channels
   - Send Messages
   - Connect (Voice)
   - Read Message History
   - Add Reactions
   - Use Slash Commands
5. Enable the following privileged gateway intents:
   - Presence Intent
   - Server Members Intent
   - Message Content Intent

### Step 5: Run the Bot
```bash
python bot.py
```

## ⚙️ Configuration Files

### `watchlist.json`
Controls which users are monitored for offline notifications:
```json
{
  "watch_everyone": false,
  "watched_user_ids": [123456789, 987654321],
  "offline_message": "<@{user_id}> went offline!"
}
```
- `watch_everyone`: If `true`, monitors all server members
- `watched_user_ids`: Specific user IDs to monitor (ignored if `watch_everyone` is `true`)
- `offline_message`: Custom message sent when user goes offline (supports `{user_id}` placeholder)

### `ignore.json`
Controls which users are excluded from the leaderboard:
```json
{
  "ignored_user_ids": [123456789, 987654321]
}
```
- `ignored_user_ids`: Array of user IDs to exclude from voice chat tracking and leaderboard

### `memory.json` (Auto-generated)
Stores voice chat tracking data:
```json
{
  "user_id": {
    "username": "username",
    "total_time": 3600,
    "in_voice": false
  }
}
```

## 🏗️ Project Structure

```
discord-offlinepresence-detector/
├── bot.py                 # Main bot file
├── commands/              # Command modules
│   ├── backup.py         # Backup file management
│   ├── ignore.py         # Ignore list management
│   ├── leaderboard.py    # Voice chat leaderboard
│   ├── listid.py         # User ID listing
│   ├── restart.py        # Bot restart functionality
│   ├── update.py         # Git update functionality
│   └── watchlist.py      # Watchlist management
├── backup/               # Automatic backup storage
├── .env                  # Environment variables (create from .env.example)
├── .env.example          # Environment template
├── requirements.txt      # Python dependencies
├── watchlist.json        # Watchlist configuration
├── ignore.json           # Ignore list configuration
└── memory.json           # Voice tracking data (auto-generated)
```

## 🔧 Technical Details

### Voice Chat Tracking
- Monitors `on_voice_state_update` events
- Tracks join/leave times with high precision
- Automatically saves data every minute and on bot shutdown
- Handles edge cases like bot restarts and network interruptions

### Presence Monitoring
- Uses both message-based and reaction-based detection
- Configurable cooldown periods to prevent spam
- Supports custom offline messages with user mentions
- Real-time configuration reloading without bot restart

### Backup System
- Automatic daily backups at midnight
- Timestamp-based file naming: `memory-YYYY-MM-DD-HHMM.json`
- Manual backup downloads via `!backup` command
- File size validation for Discord upload limits

### Data Persistence
- JSON-based storage for simplicity and portability
- Atomic file operations to prevent data corruption
- Graceful error handling for file I/O operations
- Automatic data migration and validation

## 🔒 Permissions & Security

### Required Bot Permissions
- **Read Messages/View Channels**: Basic message reading
- **Send Messages**: Command responses and notifications
- **Connect**: Voice channel monitoring
- **Read Message History**: Reaction event handling
- **Add Reactions**: Interactive features

### Administrative Access
- Most management commands require "Manage Server" permission
- User ID validation and error handling
- Comprehensive logging for audit trails
- Safe file operations with proper error handling

## 📊 Monitoring & Logging

- Comprehensive logging system with timestamps
- Command usage tracking
- Error logging with stack traces
- Performance monitoring for voice state updates
- Audit trail for administrative actions

## 🚨 Troubleshooting

### Common Issues

**Bot not responding to commands:**
- Verify bot has proper permissions in the channel
- Check if Message Content Intent is enabled
- Ensure bot token is correct in `.env` file

**Voice tracking not working:**
- Verify Voice State Intent is enabled
- Check bot has Connect permission in voice channels
- Ensure bot can see the voice channels

**Configuration changes not taking effect:**
- Use management commands to modify watchlist/ignore lists
- Avoid manually editing JSON files while bot is running
- Check file permissions and JSON syntax

**Backup files not generating:**
- Verify write permissions in the project directory
- Check available disk space
- Review logs for backup-related errors

### Log Files
The bot uses Python's logging module with INFO level by default. Logs include:
- Bot startup and shutdown events
- Command executions with user information
- Voice state changes and tracking updates
- Configuration changes and file operations
- Error messages with detailed stack traces

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is open source. Please check the repository for license details.

## 🆘 Support

For issues, questions, or feature requests, please open an issue on the GitHub repository.
