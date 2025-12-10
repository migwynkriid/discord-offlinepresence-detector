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
from commands.afkchannel import setup_afkchannel

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

# Load AFK channels configuration from afkchannels.json
def load_afk_channels():
    """Load AFK channel IDs from afkchannels.json file"""
    try:
        with open('afkchannels.json', 'r') as f:
            data = json.load(f)
            return data.get('afk_channel_ids', [])
    except (FileNotFoundError, json.JSONDecodeError):
        logging.warning("afkchannels.json not found or invalid, using empty AFK channels list")
        return []

# List of user IDs to ignore in voice tracking
IGNORED_USER_IDS = load_ignored_users()

# Watchlist configuration
WATCHLIST_CONFIG = load_watchlist_config()

# AFK channels configuration
AFK_CHANNEL_IDS = load_afk_channels()

def reload_watchlist_config():
    """Reload the watchlist configuration from file."""
    global WATCHLIST_CONFIG
    WATCHLIST_CONFIG = load_watchlist_config()

def reload_ignored_users():
    """Reload the ignored users list from file."""
    global IGNORED_USER_IDS, voice_time_tracking
    IGNORED_USER_IDS = load_ignored_users()
    logging.info(f"Reloaded ignore list: {IGNORED_USER_IDS}")
    
    # Remove ignored users from voice_time_tracking
    users_to_remove = [user_id for user_id in voice_time_tracking.keys() 
                       if int(user_id) in IGNORED_USER_IDS]
    
    logging.info(f"Found {len(users_to_remove)} ignored users to remove from tracking")
    for user_id in users_to_remove:
        username = voice_time_tracking[user_id].get('username', 'Unknown')
        del voice_time_tracking[user_id]
        logging.info(f"Removed ignored user {user_id} ({username}) from voice tracking")
    
    if users_to_remove:
        save_memory()
        logging.info("Saved memory after removing ignored users")

def reload_afk_channels():
    """Reload the AFK channels list from file."""
    global AFK_CHANNEL_IDS
    AFK_CHANNEL_IDS = load_afk_channels()

def get_ignored_users():
    """Get the current ignored users list."""
    return IGNORED_USER_IDS

# Load voice tracking data from memory.json if it exists
try:
    with open('memory.json', 'r') as f:
        voice_time_tracking = json.load(f)
    
    logging.info(f"Loaded {len(voice_time_tracking)} users from memory.json")
    logging.info(f"Ignored users list: {IGNORED_USER_IDS}")
    
    # Clean up any ignored users from loaded data
    users_to_remove = [user_id for user_id in voice_time_tracking.keys() 
                       if int(user_id) in IGNORED_USER_IDS]
    
    logging.info(f"Startup cleanup: Found {len(users_to_remove)} ignored users to remove")
    for user_id in users_to_remove:
        username = voice_time_tracking[user_id].get('username', 'Unknown')
        del voice_time_tracking[user_id]
        logging.info(f"Startup cleanup: Removed ignored user {user_id} ({username})")
    
    if users_to_remove:
        # Save the cleaned up memory immediately
        with open('memory.json', 'w') as f:
            json.dump(voice_time_tracking, f, indent=4)
        logging.info("Startup cleanup: Saved cleaned memory.json")
except (FileNotFoundError, json.JSONDecodeError):
    voice_time_tracking = {}

def save_memory():
    """Save voice tracking data to memory.json"""
    with open('memory.json', 'w') as f:
        json.dump(voice_time_tracking, f, indent=4)

def update_voice_times():
    """Update voice times for users currently being tracked in voice channels (only those with multiple people)."""
    current_time = datetime.now().timestamp()
    
    # Update time for users currently being tracked in voice channels
    # Only users with 'join_time' are being actively tracked (not alone)
    for user_id, time_data in voice_time_tracking.items():
        if time_data.get('in_voice', False) and 'join_time' in time_data:
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

def organize_backup_files():
    """Organize backup files into year/month/day subdirectories"""
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backup')
    
    if not os.path.exists(backup_dir):
        return
    
    # Get all .json files in the backup directory (not in subdirectories)
    json_files = []
    for file in os.listdir(backup_dir):
        file_path = os.path.join(backup_dir, file)
        if os.path.isfile(file_path) and file.endswith('.json') and file.startswith('memory-'):
            json_files.append(file)
    
    organized_count = 0
    
    for filename in json_files:
        # Parse filename: memory-YEAR-MONTH-DAY-COUNT.json
        try:
            # Remove 'memory-' prefix and '.json' suffix
            date_part = filename[7:-5]  # Remove 'memory-' and '.json'
            
            # Split by '-' to get year, month, day, count
            parts = date_part.split('-')
            if len(parts) >= 4:
                year = parts[0]
                month = parts[1]
                day = parts[2]
                
                # Create year directory
                year_dir = os.path.join(backup_dir, year)
                os.makedirs(year_dir, exist_ok=True)
                
                # Create month directory
                month_dir = os.path.join(year_dir, month)
                os.makedirs(month_dir, exist_ok=True)
                
                # Create day directory
                day_dir = os.path.join(month_dir, day)
                os.makedirs(day_dir, exist_ok=True)
                
                # Move file to day directory
                old_path = os.path.join(backup_dir, filename)
                new_path = os.path.join(day_dir, filename)
                
                if not os.path.exists(new_path):
                    shutil.move(old_path, new_path)
                    organized_count += 1
                    logging.info(f"Organized backup file: {filename} -> {year}/{month}/{day}/")
                
        except (ValueError, IndexError) as e:
            logging.warning(f"Could not parse backup filename: {filename} - {e}")
            continue
    
    if organized_count > 0:
        logging.info(f"Organized {organized_count} backup files into subdirectories")

def backup_memory():
    """Create a backup of memory.json with date in filename in organized directory structure"""
    # Create backup directory if it doesn't exist
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backup')
    os.makedirs(backup_dir, exist_ok=True)
    
    # Generate backup filename with current date and time
    current_datetime = datetime.now()
    year = current_datetime.strftime('%Y')
    month = current_datetime.strftime('%m')
    day = current_datetime.strftime('%d')
    time_str = current_datetime.strftime('%H%M')
    
    # Create organized directory structure
    year_dir = os.path.join(backup_dir, year)
    os.makedirs(year_dir, exist_ok=True)
    
    month_dir = os.path.join(year_dir, month)
    os.makedirs(month_dir, exist_ok=True)
    
    day_dir = os.path.join(month_dir, day)
    os.makedirs(day_dir, exist_ok=True)
    
    # Generate backup filename and path in organized structure
    backup_filename = f'memory-{year}-{month}-{day}-{time_str}.json'
    backup_path = os.path.join(day_dir, backup_filename)
    
    # Copy the file
    shutil.copy2('memory.json', backup_path)
    logging.info(f"Created backup: {backup_filename} in {year}/{month}/{day}/")

def reset_counters():
    """Reset all users' total_time to 0"""
    logging.info("Resetting daily voice time counters...")
    # Create backup before reset
    backup_memory()
    for user_id in voice_time_tracking:
        voice_time_tracking[user_id]['total_time'] = 0
    save_memory()

@tasks.loop(minutes=120)
async def periodic_update():
    """Task that runs every 2 hours to update voice times, create backup, and check for daily reset."""
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
    
    # Organize backup files into subdirectories
    organize_backup_files()
    
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
            for member in voice_channel.members:
                # Skip ignored users
                if member.id in IGNORED_USER_IDS:
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
                logging.info(f"Found user {member.name} in channel {voice_channel.name}")
    
    save_memory()
    periodic_update.start()  # Start the periodic update task

# Setup commands
setup_leaderboard(bot, voice_time_tracking, get_ignored_users, update_voice_times)
setup_restart(bot, save_memory, periodic_update, update_voice_times)
setup_update(bot, save_memory, periodic_update, update_voice_times)
setup_watchlist(bot)
setup_ignore(bot, reload_ignored_users)
setup_listid(bot)
setup_backup(bot)
setup_afkchannel(bot, reload_afk_channels)

@bot.event
async def on_voice_state_update(member, before, after):
    """Track time spent in voice channels, but only when there are multiple people in the channel and not in AFK channels."""
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
        # Check if the channel is an AFK channel - if so, don't track time
        if before.channel.id not in AFK_CHANNEL_IDS:
            if voice_time_tracking[member_id].get('in_voice', False):
                if 'join_time' in voice_time_tracking[member_id]:
                    # Only count time if there were multiple people in the channel
                    # Check if there are still other members in the channel after this user left
                    remaining_members = [m for m in before.channel.members if m.id != member.id and m.id not in get_ignored_users()]
                    if len(remaining_members) >= 1:  # There were at least 2 people (including the leaving member)
                        time_spent = current_time - voice_time_tracking[member_id]['join_time']
                        voice_time_tracking[member_id]['total_time'] += time_spent
                    del voice_time_tracking[member_id]['join_time']
        
        # Always update in_voice status regardless of AFK channel
        voice_time_tracking[member_id]['in_voice'] = False
        # Clean up join_time if it exists when leaving any channel
        if 'join_time' in voice_time_tracking[member_id]:
            del voice_time_tracking[member_id]['join_time']
        save_memory()
    
    # Handle joining voice channel
    if after and after.channel:
        logging.info(f"VOICE JOIN EVENT: {member.name} joined channel '{after.channel.name}' - checking ALL members")
        # Check if the channel is an AFK channel - if so, don't track time
        if after.channel.id in AFK_CHANNEL_IDS:
            # Mark as in voice but don't track time in AFK channels
            voice_time_tracking[member_id]['in_voice'] = True
            # Remove join_time if it exists to prevent tracking
            if 'join_time' in voice_time_tracking[member_id]:
                del voice_time_tracking[member_id]['join_time']
            logging.info(f"User joined AFK channel - marked as in voice but not tracked")
        else:
            # Count non-ignored members in the channel (including the joining member)
            non_ignored_members = [m for m in after.channel.members if m.id not in get_ignored_users()]
            
            # Only start tracking if there are multiple people in the channel
            if len(non_ignored_members) >= 2:
                voice_time_tracking[member_id]['join_time'] = current_time
                voice_time_tracking[member_id]['in_voice'] = True
                logging.info(f"Started tracking for {member.name} (channel now has {len(non_ignored_members)} members)")
            else:
                # If alone, mark as in voice but don't set join_time (no tracking)
                voice_time_tracking[member_id]['in_voice'] = True
                # Remove join_time if it exists to prevent tracking
                if 'join_time' in voice_time_tracking[member_id]:
                    del voice_time_tracking[member_id]['join_time']
                logging.info(f"User is alone in channel - marked as in voice but not tracked")
        save_memory()
    
    # Handle case where someone joins/leaves and affects tracking for others
    # CRITICAL: Check ALL members' status on every voice channel change
    channels_to_update = set()
    if before and before.channel:
        channels_to_update.add(before.channel)
    if after and after.channel:
        channels_to_update.add(after.channel)
    
    # Update tracking for affected channels - this checks EVERY member in each channel
    for channel in channels_to_update:
        await update_tracking_for_specific_channel(channel)
        # Log for verification that all members are being checked
        member_count = len([m for m in channel.members if m.id not in get_ignored_users()])
        logging.info(f"Voice channel update: Checked status for {member_count} members in channel '{channel.name}'")
    
    # Also run the global update to catch any edge cases and ensure comprehensive coverage
    await update_tracking_for_channel_changes()

async def update_tracking_for_specific_channel(channel):
    """
    COMPREHENSIVE STATUS CHECK: Update tracking status for ALL users in a specific voice channel.
    This function checks EVERY SINGLE MEMBER in the channel and updates their status accordingly.
    """
    if not channel:
        return
        
    current_time = datetime.now().timestamp()
    members_checked = 0
    members_updated = 0
    
    # Skip AFK channels - no tracking should occur in these channels
    if channel.id in AFK_CHANNEL_IDS:
        logging.info(f"Processing AFK channel '{channel.name}' - ensuring no tracking occurs")
        # For users in AFK channels, ensure they're not being tracked
        for member in channel.members:
            if not member.bot and member.id not in get_ignored_users():
                members_checked += 1
                member_id = str(member.id)
                # Initialize user data if not exists
                if member_id not in voice_time_tracking:
                    voice_time_tracking[member_id] = {
                        'username': member.name,
                        'total_time': 0,
                        'in_voice': True
                    }
                    members_updated += 1
                else:
                    # Ensure they're marked as in voice but not tracked
                    voice_time_tracking[member_id]['in_voice'] = True
                    if 'join_time' in voice_time_tracking[member_id]:
                        # Stop tracking if they were being tracked
                        del voice_time_tracking[member_id]['join_time']
                        members_updated += 1
        logging.info(f"AFK channel check complete: {members_checked} members checked, {members_updated} members updated")
        save_memory()
        return
    
    non_ignored_members = [m for m in channel.members if m.id not in get_ignored_users()]
    logging.info(f"Checking ALL {len(non_ignored_members)} members in channel '{channel.name}' for status updates")
    
    # CRITICAL: Check EVERY SINGLE MEMBER in the channel (except ignored users)
    for member in channel.members:
        # Skip ignored users
        if member.id in get_ignored_users():
            continue
            
        members_checked += 1
        member_id = str(member.id)
        
        # Initialize user data if not exists
        if member_id not in voice_time_tracking:
            voice_time_tracking[member_id] = {
                'username': member.name,
                'total_time': 0,
                'in_voice': True  # They're in voice since we're processing them
            }
            members_updated += 1
            logging.debug(f"Initialized new user data for {member.name}")
        else:
            # Ensure they're marked as in voice
            voice_time_tracking[member_id]['in_voice'] = True
        
        # Determine if tracking should be active based on member count
        should_track = len(non_ignored_members) >= 2
        is_currently_tracking = 'join_time' in voice_time_tracking[member_id]
        
        if should_track and not is_currently_tracking:
            # Should be tracking but isn't - start tracking
            voice_time_tracking[member_id]['join_time'] = current_time
            members_updated += 1
            logging.debug(f"Started tracking for {member.name} (channel has {len(non_ignored_members)} members)")
        elif not should_track and is_currently_tracking:
            # Shouldn't be tracking but is - stop tracking and save time
            time_spent = current_time - voice_time_tracking[member_id]['join_time']
            voice_time_tracking[member_id]['total_time'] += time_spent
            del voice_time_tracking[member_id]['join_time']
            members_updated += 1
            logging.debug(f"Stopped tracking for {member.name} (channel has {len(non_ignored_members)} members)")
    
    logging.info(f"Channel status check complete: {members_checked} members checked, {members_updated} members updated")
    save_memory()

async def update_tracking_for_channel_changes():
    """Update tracking status for all users based on current voice channel member counts, excluding AFK channels."""
    current_time = datetime.now().timestamp()
    
    # Get all guilds the bot is in
    for guild in bot.guilds:
        # Check all voice channels in the guild
        for channel in guild.voice_channels:
            # Skip AFK channels - no tracking should occur in these channels
            if channel.id in AFK_CHANNEL_IDS:
                # For users in AFK channels, ensure they're not being tracked
                for member in channel.members:
                    if member.id not in get_ignored_users():
                        member_id = str(member.id)
                        # Initialize user data if not exists
                        if member_id not in voice_time_tracking:
                            voice_time_tracking[member_id] = {
                                'username': member.name,
                                'total_time': 0,
                                'in_voice': True
                            }
                        else:
                            # Ensure they're marked as in voice but not tracked
                            voice_time_tracking[member_id]['in_voice'] = True
                            if 'join_time' in voice_time_tracking[member_id]:
                                # Stop tracking if they were being tracked
                                del voice_time_tracking[member_id]['join_time']
                continue
            
            non_ignored_members = [m for m in channel.members if m.id not in get_ignored_users()]
            
            # For each member in the channel
            for member in channel.members:
                if member.id in get_ignored_users():
                    continue
                    
                member_id = str(member.id)
                
                # Initialize user data if not exists
                if member_id not in voice_time_tracking:
                    voice_time_tracking[member_id] = {
                        'username': member.name,
                        'total_time': 0,
                        'in_voice': True  # They're in voice since we're processing them
                    }
                else:
                    # Ensure they're marked as in voice
                    voice_time_tracking[member_id]['in_voice'] = True
                
                # Determine if tracking should be active based on member count
                should_track = len(non_ignored_members) >= 2
                is_currently_tracking = 'join_time' in voice_time_tracking[member_id]
                
                if should_track and not is_currently_tracking:
                    # Should be tracking but isn't - start tracking
                    voice_time_tracking[member_id]['join_time'] = current_time
                elif not should_track and is_currently_tracking:
                    # Shouldn't be tracking but is - stop tracking and save time
                    time_spent = current_time - voice_time_tracking[member_id]['join_time']
                    voice_time_tracking[member_id]['total_time'] += time_spent
                    del voice_time_tracking[member_id]['join_time']
    
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
