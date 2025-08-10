import os
import sys
import signal
import asyncio
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import subprocess
from datetime import datetime, timedelta
import json
import logging
import pytz  # Add pytz for timezone handling
import shutil
from commands.leaderboard import setup_leaderboard
from commands.restart import setup_restart
from commands.update import setup_update
from commands.watchlist import setup_watchlist
from commands.ignore import setup_ignore
from commands.listid import setup_listid
from commands.backup import setup_backup

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables from .env file
load_dotenv()

# Bot configuration
intents = discord.Intents.default()
intents.members = True
intents.presences = True
intents.message_content = True
intents.reactions = True
intents.guild_messages = True
intents.voice_states = True  # Enable voice state updates

# Initialize bot with prefix '!' and required intents
bot = commands.Bot(command_prefix='!', intents=intents)

# Dictionary to store the last message time for each user
last_message_time = {}

# Load ignored user IDs from ignore.json
def load_ignored_users():
    """Load ignored user IDs from ignore.json file"""
    try:
        with open('ignore.json', 'r') as f:
            data = json.load(f)
            return data.get('ignored_user_ids', [])
    except (FileNotFoundError, json.JSONDecodeError):
        logging.warning("ignore.json not found or invalid, using empty ignore list")
        return []

# Load watchlist configuration from watchlist.json
def load_watchlist_config():
    """Load watchlist configuration from watchlist.json file"""
    try:
        with open('watchlist.json', 'r') as f:
            data = json.load(f)
            return {
                'watch_everyone': data.get('watch_everyone', False),
                'watched_user_ids': data.get('watched_user_ids', []),
                'offline_message': data.get('offline_message', '<@{user_id}> is now offline')
            }
    except (FileNotFoundError, json.JSONDecodeError):
        logging.warning("watchlist.json not found or invalid, using default config")
        return {
            'watch_everyone': False, 
            'watched_user_ids': [],
            'offline_message': '<@{user_id}> is now offline'
        }

# List of user IDs to ignore in voice tracking
IGNORED_USER_IDS = load_ignored_users()

# Watchlist configuration
WATCHLIST_CONFIG = load_watchlist_config()

def reload_watchlist_config():
    """Reload the watchlist configuration from file."""
    global WATCHLIST_CONFIG
    WATCHLIST_CONFIG = load_watchlist_config()

def reload_ignored_users():
    """Reload the ignored users list from file."""
    global IGNORED_USER_IDS
    IGNORED_USER_IDS = load_ignored_users()

def get_ignored_users():
    """Get the current ignored users list."""
    return IGNORED_USER_IDS

# Load voice tracking data from memory.json if it exists
try:
    with open('memory.json', 'r') as f:
        voice_time_tracking = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    voice_time_tracking = {}

def save_memory():
    """Save voice tracking data to memory.json"""
    with open('memory.json', 'w') as f:
        json.dump(voice_time_tracking, f, indent=4)

def update_voice_times():
    """Update voice times for users currently in voice channels."""
    current_time = datetime.now().timestamp()
    
    # Get all voice channels and their member counts
    voice_channel_members = {}
    for guild in bot.guilds:
        for voice_channel in guild.voice_channels:
            voice_channel_members[voice_channel.id] = len(voice_channel.members)
    
    # Update time for users currently in voice channels
    for user_id, time_data in voice_time_tracking.items():
        if time_data.get('in_voice', False) and 'join_time' in time_data:
            # Find which voice channel this user is in
            user_voice_channel = None
            for guild in bot.guilds:
                member = guild.get_member(int(user_id))
                if member and member.voice and member.voice.channel:
                    user_voice_channel = member.voice.channel
                    break
            
            # Only count time if there are 2 or more users in the voice channel
            if user_voice_channel and voice_channel_members.get(user_voice_channel.id, 0) >= 2:
                time_spent = current_time - time_data['join_time']
                time_data['total_time'] += time_spent
            
            time_data['join_time'] = current_time  # Reset join time to current time
    
    save_memory()

def should_reset():
    """Check if it's time to reset the counters (00:10 CET)"""
    cet = pytz.timezone('CET')
    current_time = datetime.now(cet)
    reset_time = current_time.replace(hour=0, minute=10, second=0, microsecond=0)
    
    # If current time is past reset time but before reset time + 1 minute
    if current_time >= reset_time and current_time < reset_time + timedelta(minutes=1):
        return True
    return False

def backup_memory():
    """Create a backup of memory.json with date in filename"""
    # Create backup directory if it doesn't exist
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backup')
    os.makedirs(backup_dir, exist_ok=True)
    
    # Generate backup filename with current date and time
    current_datetime = datetime.now().strftime('%Y-%m-%d-%H%M')
    backup_filename = f'memory-{current_datetime}.json'
    backup_path = os.path.join(backup_dir, backup_filename)
    
    # Copy the file
    shutil.copy2('memory.json', backup_path)
    logging.info(f"Created backup: {backup_filename}")

def reset_counters():
    """Reset all users' total_time to 0"""
    logging.info("Resetting daily voice time counters...")
    # Create backup before reset
    backup_memory()
    for user_id in voice_time_tracking:
        voice_time_tracking[user_id]['total_time'] = 0
    save_memory()

@tasks.loop(minutes=1440)
async def periodic_update():
    """Task that runs every minute to update voice times, create backup, and check for daily reset."""
    logging.info("Updating voice chat times...")
    update_voice_times()
    
    # Create backup
    backup_memory()
    
    if should_reset():
        reset_counters()
        # Log the reset
        logging.info("Daily voice time counters have been reset")

@bot.event
async def on_ready():
    """Event handler for when the bot is ready and connected to Discord."""
    logging.info(f'{bot.user} has connected to Discord!')
    logging.info(f'Bot is in {len(bot.guilds)} guilds')
    
    # Reload ignored users and watchlist config to ensure they're up to date
    reload_ignored_users()
    reload_watchlist_config()
    logging.info(f'Loaded {len(IGNORED_USER_IDS)} ignored users from ignore.json')
    
    # Check all users marked as in_voice
    for guild in bot.guilds:
        voice_members = set()
        for voice_channel in guild.voice_channels:
            for member in voice_channel.members:
                voice_members.add(str(member.id))
        
        # Update voice_time_tracking for users not actually in voice
        for user_id, data in voice_time_tracking.items():
            if data.get('in_voice', False) and user_id not in voice_members:
                current_time = datetime.now().timestamp()
                if 'join_time' in data:
                    time_spent = current_time - data['join_time']
                    data['total_time'] += time_spent
                    del data['join_time']
                data['in_voice'] = False
        save_memory()
    
    # Check for users already in voice channels
    current_time = datetime.now().timestamp()
    for guild in bot.guilds:
        for voice_channel in guild.voice_channels:
            # Only track users in channels with 2 or more members
            if len(voice_channel.members) >= 2:
                for member in voice_channel.members:
                    # Skip ignored users
                    if member.id in get_ignored_users():
                        continue
                        
                    member_id = str(member.id)
                    if member_id not in voice_time_tracking:
                        voice_time_tracking[member_id] = {
                            'username': member.name,
                            'total_time': 0,
                            'in_voice': False
                        }
                    
                    # Update status and join time for users already in voice
                    voice_time_tracking[member_id]['in_voice'] = True
                    voice_time_tracking[member_id]['join_time'] = current_time
                    logging.info(f"Found user {member.name} in channel {voice_channel.name} with {len(voice_channel.members)} members")
    
    save_memory()
    periodic_update.start()  # Start the periodic update task

# Setup commands
setup_leaderboard(bot, voice_time_tracking, get_ignored_users, update_voice_times)
setup_restart(bot, save_memory, periodic_update)
setup_update(bot, save_memory, periodic_update)
setup_watchlist(bot)
setup_ignore(bot, reload_ignored_users)
setup_listid(bot)
setup_backup(bot)

@bot.event
async def on_voice_state_update(member, before, after):
    """Track time spent in voice channels."""
    # Ignore specified users
    if member.id in get_ignored_users():
        return
        
    current_time = datetime.now().timestamp()
    member_id = str(member.id)
    
    # Initialize user data if not exists
    if member_id not in voice_time_tracking:
        voice_time_tracking[member_id] = {
            'username': member.name,
            'total_time': 0,
            'in_voice': False
        }
    
    # Handle leaving voice channel
    if before and before.channel:
        if voice_time_tracking[member_id].get('in_voice', False):
            if 'join_time' in voice_time_tracking[member_id]:
                # Only count time if there were 2 or more users in the voice channel
                # Check current member count (including the user who is leaving)
                current_member_count = len(before.channel.members)
                if current_member_count >= 2:
                    time_spent = current_time - voice_time_tracking[member_id]['join_time']
                    voice_time_tracking[member_id]['total_time'] += time_spent
                del voice_time_tracking[member_id]['join_time']
            voice_time_tracking[member_id]['in_voice'] = False
            save_memory()
    
    # Handle joining voice channel
    if after and after.channel:
        voice_time_tracking[member_id]['join_time'] = current_time
        voice_time_tracking[member_id]['in_voice'] = True
        save_memory()

async def check_and_respond(user_id, channel):
    """Common function to check user status and respond if needed."""
    member = channel.guild.get_member(user_id)
    
    # Check if we should watch this user based on watchlist configuration
    should_watch = False
    if WATCHLIST_CONFIG['watch_everyone']:
        should_watch = True
    elif member and member.id in WATCHLIST_CONFIG['watched_user_ids']:
        should_watch = True
    
    if member and should_watch:
        current_time = datetime.now()
        last_time = last_message_time.get(member.id)
        
        if last_time is None or (current_time - last_time) > timedelta(days=1):
            if member.status in [discord.Status.offline, discord.Status.invisible]:
                message = WATCHLIST_CONFIG['offline_message'].format(user_id=member.id)
                await channel.send(message)
                last_message_time[member.id] = current_time

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    await check_and_respond(message.author.id, message.channel)
    await bot.process_commands(message)

@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return
    await check_and_respond(user.id, reaction.message.channel)

@bot.event
async def on_reaction_remove(reaction, user):
    if user.bot:
        return
    await check_and_respond(user.id, reaction.message.channel)

@bot.event
async def on_raw_reaction_add(payload):
    if bot.user and payload.user_id != bot.user.id:
        channel = bot.get_channel(payload.channel_id)
        if channel:
            await check_and_respond(payload.user_id, channel)

@bot.event
async def on_raw_reaction_remove(payload):
    if bot.user and payload.user_id != bot.user.id:
        channel = bot.get_channel(payload.channel_id)
        if channel:
            await check_and_respond(payload.user_id, channel)

# Global flag to control shutdown
shutdown_requested = False

async def graceful_shutdown():
    """Perform graceful shutdown of the bot."""
    global shutdown_requested
    shutdown_requested = True
    
    logging.info("Graceful shutdown initiated...")
    
    # Save current state
    save_memory()
    
    # Stop periodic tasks
    if periodic_update.is_running():
        periodic_update.stop()
        logging.info("Stopped periodic update task")
    
    # Close the bot connection
    if not bot.is_closed():
        await bot.close()
        logging.info("Bot connection closed")
    
    logging.info("Graceful shutdown completed")

def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logging.info(f"Received signal {signum}, initiating shutdown...")
    # Create a new event loop if one doesn't exist
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    # Schedule graceful shutdown
    if loop.is_running():
        loop.create_task(graceful_shutdown())
    else:
        loop.run_until_complete(graceful_shutdown())
    
    # Force exit
    sys.exit(0)

async def main():
    """Main function to run the bot with proper shutdown handling."""
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Termination signal
    
    # Get the token from environment variables
    TOKEN = os.getenv('DISCORD_TOKEN')
    if not TOKEN:
        raise ValueError("No Discord token found. Make sure to set DISCORD_TOKEN in your .env file")
    
    try:
        logging.info("Starting bot...")
        await bot.start(TOKEN)
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt received, shutting down...")
        await graceful_shutdown()
    except Exception as e:
        logging.error(f"Bot encountered an error: {e}")
        await graceful_shutdown()
        raise
    finally:
        if not bot.is_closed():
            await bot.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot shutdown completed")
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        sys.exit(1)
