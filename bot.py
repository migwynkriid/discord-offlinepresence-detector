from __future__ import annotations

import os
import sys
import signal
import asyncio
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
from datetime import datetime, timedelta
import json
import logging
import pytz
import shutil
import threading
import aiofiles
import aiofiles.os
from typing import Any, TypedDict, Optional
from commands.leaderboard import setup_leaderboard
from commands.restart import setup_restart
from commands.update import setup_update
from commands.watchlist import setup_watchlist
from commands.ignore import setup_ignore
from commands.listid import setup_listid
from commands.backup import setup_backup
from commands.afkchannel import setup_afkchannel
from commands.timeedit import setup_timeedit


# Type definitions
class VoiceTrackingData(TypedDict, total=False):
    username: str
    total_time: float
    in_voice: bool
    join_time: float


class WatchlistConfig(TypedDict):
    watch_everyone: bool
    watched_user_ids: list[int]
    offline_message: str
    on_join_messages: dict[str, str]


class BotConfig(TypedDict):
    activity: str


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
last_message_time: dict[int, datetime] = {}

# Dictionary to store the last on-join message time for each user (rate limit: once per day)
last_on_join_message_time: dict[int, datetime] = {}


def cleanup_rate_limit_dicts() -> None:
    """Remove entries older than 2 days from rate limit dictionaries to prevent memory leaks."""
    current_time = datetime.now()
    cutoff = timedelta(days=2)
    
    # Clean up last_message_time
    expired_keys = [k for k, v in last_message_time.items() if (current_time - v) > cutoff]
    for key in expired_keys:
        del last_message_time[key]
    
    # Clean up last_on_join_message_time
    expired_keys = [k for k, v in last_on_join_message_time.items() if (current_time - v) > cutoff]
    for key in expired_keys:
        del last_on_join_message_time[key]
    
    if expired_keys:
        logging.info(f"Cleaned up {len(expired_keys)} expired rate limit entries")


def load_ignored_users() -> list[int]:
    """Load ignored user IDs from ignore.json file."""
    try:
        with open('ignore.json', 'r') as f:
            data = json.load(f)
            return data.get('ignored_user_ids', [])
    except (FileNotFoundError, json.JSONDecodeError):
        logging.warning("ignore.json not found or invalid, using empty ignore list")
        return []


def load_watchlist_config() -> WatchlistConfig:
    """Load watchlist configuration from watchlist.json file."""
    try:
        with open('watchlist.json', 'r') as f:
            data = json.load(f)
            return {
                'watch_everyone': data.get('watch_everyone', False),
                'watched_user_ids': data.get('watched_user_ids', []),
                'offline_message': data.get('offline_message', '<@{user_id}> is now offline'),
                'on_join_messages': data.get('on_join_messages', {})
            }
    except (FileNotFoundError, json.JSONDecodeError):
        logging.warning("watchlist.json not found or invalid, using default config")
        return {
            'watch_everyone': False, 
            'watched_user_ids': [],
            'offline_message': '<@{user_id}> is now offline',
            'on_join_messages': {}
        }


def load_afk_channels() -> list[int]:
    """Load AFK channel IDs from afkchannels.json file."""
    try:
        with open('afkchannels.json', 'r') as f:
            data = json.load(f)
            return data.get('afk_channel_ids', [])
    except (FileNotFoundError, json.JSONDecodeError):
        logging.warning("afkchannels.json not found or invalid, using empty AFK channels list")
        return []


def load_bot_config() -> BotConfig:
    """Load bot configuration from config.json file."""
    try:
        with open('config.json', 'r') as f:
            data = json.load(f)
            return {
                'activity': data.get('activity', 'watching your dumbass')
            }
    except (FileNotFoundError, json.JSONDecodeError):
        logging.warning("config.json not found or invalid, using default config")
        return {
            'activity': 'watching your dumbass'
        }


# Global state
IGNORED_USER_IDS: list[int] = load_ignored_users()
WATCHLIST_CONFIG: WatchlistConfig = load_watchlist_config()
AFK_CHANNEL_IDS: list[int] = load_afk_channels()
BOT_CONFIG: BotConfig = load_bot_config()


def reload_watchlist_config() -> None:
    """Reload the watchlist configuration from file."""
    global WATCHLIST_CONFIG
    WATCHLIST_CONFIG = load_watchlist_config()

def reload_ignored_users() -> None:
    """Reload the ignored users list from file."""
    global IGNORED_USER_IDS
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
        asyncio.create_task(async_save_memory())
        logging.info("Saved memory after removing ignored users")


def reload_afk_channels() -> None:
    """Reload the AFK channels list from file."""
    global AFK_CHANNEL_IDS
    AFK_CHANNEL_IDS = load_afk_channels()


def get_ignored_users() -> list[int]:
    """Get the current ignored users list."""
    return IGNORED_USER_IDS


def is_muted_and_deafened(member: discord.Member) -> bool:
    """Check if a member is both muted AND deafened (either self or server).
    
    Users who are both muted AND deafened should not be tracked.
    """
    if not member.voice:
        return False
    
    # Check if muted (either self-muted or server-muted)
    is_muted = member.voice.self_mute or member.voice.mute
    
    # Check if deafened (either self-deafened or server-deafened)
    is_deafened = member.voice.self_deaf or member.voice.deaf
    
    # Return True only if BOTH muted AND deafened
    return is_muted and is_deafened

# Load voice tracking data from memory.json if it exists
def _load_voice_tracking_sync() -> dict[str, VoiceTrackingData]:
    """Synchronously load voice tracking data (used at startup only)."""
    try:
        with open('memory.json', 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


voice_time_tracking: dict[str, VoiceTrackingData] = _load_voice_tracking_sync()

# Startup cleanup
if voice_time_tracking:
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
        # Save the cleaned up memory immediately (sync at startup is fine)
        with open('memory.json', 'w') as f:
            json.dump(voice_time_tracking, f, indent=4)
        logging.info("Startup cleanup: Saved cleaned memory.json")

# Async file lock
_save_lock = asyncio.Lock()


async def async_save_memory() -> None:
    """Save voice tracking data to memory.json asynchronously with proper error handling."""
    async with _save_lock:
        try:
            temp_path = 'memory.json.tmp'
            content = json.dumps(voice_time_tracking, indent=4)
            async with aiofiles.open(temp_path, 'w') as f:
                await f.write(content)
            # Atomic rename
            if await aiofiles.os.path.exists('memory.json'):
                os.replace(temp_path, 'memory.json')
            else:
                os.rename(temp_path, 'memory.json')
        except Exception as e:
            logging.error(f"Failed to save memory.json: {e}")
            if await aiofiles.os.path.exists('memory.json.tmp'):
                try:
                    await aiofiles.os.remove('memory.json.tmp')
                except:
                    pass


def save_memory() -> None:
    """Synchronous wrapper for save - schedules async save if in event loop, else blocks."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(async_save_memory())
    except RuntimeError:
        # No event loop running, use sync version
        try:
            with open('memory.json.tmp', 'w') as f:
                json.dump(voice_time_tracking, f, indent=4)
            if os.path.exists('memory.json'):
                os.replace('memory.json.tmp', 'memory.json')
            else:
                os.rename('memory.json.tmp', 'memory.json')
        except Exception as e:
            logging.error(f"Failed to save memory.json (sync): {e}")


def update_voice_times() -> None:
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


def should_reset() -> bool:
    """Check if it's time to reset the counters (00:10 CET)."""
    cet = pytz.timezone('CET')
    current_time = datetime.now(cet)
    reset_time = current_time.replace(hour=0, minute=10, second=0, microsecond=0)
    
    # If current time is past reset time but before reset time + 1 minute
    return reset_time <= current_time < reset_time + timedelta(minutes=1)


def organize_backup_files() -> None:
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

def backup_memory() -> None:
    """Create a backup of memory.json with date in filename in organized directory structure."""
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


def reset_counters() -> None:
    """Reset all users' total_time to 0."""
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
    
    # Clean up old rate limit entries to prevent memory leaks
    cleanup_rate_limit_dicts()
    
    if should_reset():
        reset_counters()
        # Log the reset
        logging.info("Daily voice time counters have been reset")

@bot.event
async def on_ready():
    """Event handler for when the bot is ready and connected to Discord."""
    logging.info(f'{bot.user} has connected to Discord!')
    logging.info(f'Bot is in {len(bot.guilds)} guilds')
    
    # Set bot activity from config
    activity_text = BOT_CONFIG.get('activity', 'watching your dumbass')
    activity_text_lower = activity_text.lower()
    
    # Parse activity type from the start of the string
    activity_prefixes = [
        ('watching ', discord.ActivityType.watching),
        ('playing ', discord.ActivityType.playing),
        ('listening to ', discord.ActivityType.listening),
        ('competing in ', discord.ActivityType.competing),
        ('streaming ', discord.ActivityType.streaming),
    ]
    
    activity_type = discord.ActivityType.playing  # default
    activity_name = activity_text
    
    for prefix, atype in activity_prefixes:
        if activity_text_lower.startswith(prefix):
            activity_type = atype
            activity_name = activity_text[len(prefix):]
            break
    
    await bot.change_presence(activity=discord.Activity(type=activity_type, name=activity_name))
    logging.info(f'Set activity to: {activity_text}')
    
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
            # Skip AFK channels
            if voice_channel.id in AFK_CHANNEL_IDS:
                for member in voice_channel.members:
                    if member.id in IGNORED_USER_IDS:
                        continue
                    member_id = str(member.id)
                    if member_id not in voice_time_tracking:
                        voice_time_tracking[member_id] = {
                            'username': member.name,
                            'total_time': 0,
                            'in_voice': True
                        }
                    else:
                        voice_time_tracking[member_id]['in_voice'] = True
                    # Don't set join_time for AFK channels
                    logging.info(f"Found user {member.name} in AFK channel {voice_channel.name} - not tracking")
                continue
            
            # Get trackable members (not ignored, not muted+deafened)
            trackable_members = [
                m for m in voice_channel.members 
                if m.id not in IGNORED_USER_IDS and not is_muted_and_deafened(m)
            ]
            should_track = len(trackable_members) >= 2
            
            for member in voice_channel.members:
                # Skip ignored users
                if member.id in IGNORED_USER_IDS:
                    continue
                    
                member_id = str(member.id)
                if member_id not in voice_time_tracking:
                    voice_time_tracking[member_id] = {
                        'username': member.name,
                        'total_time': 0,
                        'in_voice': True
                    }
                else:
                    voice_time_tracking[member_id]['in_voice'] = True
                
                # Only set join_time if there are 2+ trackable members and user isn't muted+deafened
                if should_track and not is_muted_and_deafened(member):
                    voice_time_tracking[member_id]['join_time'] = current_time
                    logging.info(f"Found user {member.name} in channel {voice_channel.name} - tracking started")
                else:
                    # Remove join_time if it exists (user is alone or muted+deafened)
                    if 'join_time' in voice_time_tracking[member_id]:
                        del voice_time_tracking[member_id]['join_time']
                    logging.info(f"Found user {member.name} in channel {voice_channel.name} - not tracking (alone or muted+deafened)")
    
    save_memory()
    periodic_update.start()  # Start the periodic update task

# Setup commands
setup_leaderboard(bot, voice_time_tracking, get_ignored_users, update_voice_times)
setup_restart(bot, save_memory, periodic_update, update_voice_times)
setup_update(bot, save_memory, periodic_update, update_voice_times)
setup_watchlist(bot, reload_watchlist_config)
setup_ignore(bot, reload_ignored_users)
setup_listid(bot)
setup_backup(bot)
setup_afkchannel(bot, reload_afk_channels)
setup_timeedit(bot, voice_time_tracking, update_voice_times, save_memory)


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError) -> None:
    """Handle command errors globally."""
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ Command on cooldown. Try again in {error.retry_after:.1f}s")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing argument: `{error.param.name}`. Use `!help {ctx.command}` for usage.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ Invalid argument: {error}")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command.")
    elif isinstance(error, commands.CommandNotFound):
        pass  # Silently ignore unknown commands
    else:
        logging.error(f"Command error in {ctx.command}: {error}")


# ==============================================================================
# Voice Tracking Helper Functions
# ==============================================================================

def _ensure_user_tracking_entry(member: discord.Member) -> str:
    """Ensure a user has a tracking entry, creating one if needed. Returns member_id as string."""
    member_id = str(member.id)
    if member_id not in voice_time_tracking:
        voice_time_tracking[member_id] = {
            'username': member.name,
            'total_time': 0,
            'in_voice': False
        }
    return member_id


def _get_trackable_members(channel: discord.VoiceChannel) -> list[discord.Member]:
    """Get list of members in channel who can be tracked (not ignored, not muted+deafened)."""
    return [
        m for m in channel.members 
        if m.id not in get_ignored_users() and not is_muted_and_deafened(m)
    ]


def _update_member_tracking(
    member: discord.Member,
    trackable_count: int,
    current_time: float,
    is_afk_channel: bool = False
) -> bool:
    """
    Update tracking status for a single member based on channel conditions.
    
    Returns True if the member's status was updated, False otherwise.
    """
    member_id = _ensure_user_tracking_entry(member)
    updated = False
    
    # Always mark as in voice
    voice_time_tracking[member_id]['in_voice'] = True
    
    if is_afk_channel:
        # In AFK channel - stop tracking if active
        if 'join_time' in voice_time_tracking[member_id]:
            del voice_time_tracking[member_id]['join_time']
            updated = True
        return updated
    
    # Check if user should be tracked
    user_muted_deafened = is_muted_and_deafened(member)
    should_track = trackable_count >= 2 and not user_muted_deafened
    is_tracking = 'join_time' in voice_time_tracking[member_id]
    
    if should_track and not is_tracking:
        # Start tracking
        voice_time_tracking[member_id]['join_time'] = current_time
        updated = True
    elif not should_track and is_tracking:
        # Stop tracking and accumulate time
        time_spent = current_time - voice_time_tracking[member_id]['join_time']
        voice_time_tracking[member_id]['total_time'] += time_spent
        del voice_time_tracking[member_id]['join_time']
        updated = True
    
    return updated


async def _handle_voice_leave(
    member: discord.Member,
    channel: discord.VoiceChannel,
    current_time: float
) -> None:
    """Handle a member leaving a voice channel."""
    member_id = _ensure_user_tracking_entry(member)
    
    # Track time if not an AFK channel and was being tracked
    if channel.id not in AFK_CHANNEL_IDS:
        if voice_time_tracking[member_id].get('in_voice', False):
            if 'join_time' in voice_time_tracking[member_id]:
                # Only count time if there were multiple people
                remaining = [m for m in channel.members if m.id != member.id and m.id not in get_ignored_users()]
                if len(remaining) >= 1:
                    time_spent = current_time - voice_time_tracking[member_id]['join_time']
                    voice_time_tracking[member_id]['total_time'] += time_spent
                del voice_time_tracking[member_id]['join_time']
    
    # Update status
    voice_time_tracking[member_id]['in_voice'] = False
    if 'join_time' in voice_time_tracking[member_id]:
        del voice_time_tracking[member_id]['join_time']
    
    await async_save_memory()


async def _send_on_join_message(
    member: discord.Member,
    channel: discord.VoiceChannel
) -> None:
    """Send on-join message if configured for this user."""
    user_id_str = str(member.id)
    on_join_messages = WATCHLIST_CONFIG.get('on_join_messages', {})
    
    if user_id_str not in on_join_messages:
        return
    
    # Check rate limit
    current_datetime = datetime.now()
    last_sent = last_on_join_message_time.get(member.id)
    
    if last_sent is not None and (current_datetime - last_sent) <= timedelta(days=1):
        logging.info(f"Skipped on_join_message for {member.name} - already sent today")
        return
    
    # Find a text channel
    text_channel: Optional[discord.TextChannel] = None
    guild = channel.guild
    
    if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
        text_channel = guild.system_channel
    else:
        for ch in guild.text_channels:
            if ch.permissions_for(guild.me).send_messages:
                text_channel = ch
                break
    
    if text_channel:
        join_message = on_join_messages[user_id_str]
        if '{user_id}' in join_message:
            join_message = join_message.format(user_id=member.id)
        full_message = f"<@{member.id}> {join_message}"
        await text_channel.send(full_message)
        last_on_join_message_time[member.id] = current_datetime
        logging.info(f"Sent on_join_message for {member.name}: {full_message}")


async def _handle_voice_join(
    member: discord.Member,
    channel: discord.VoiceChannel,
    current_time: float,
    is_new_join: bool
) -> None:
    """Handle a member joining a voice channel."""
    member_id = _ensure_user_tracking_entry(member)
    
    logging.info(f"VOICE JOIN EVENT: {member.name} joined channel '{channel.name}'")
    
    # Send on-join message if applicable
    if is_new_join:
        await _send_on_join_message(member, channel)
    
    # Handle AFK channel
    if channel.id in AFK_CHANNEL_IDS:
        voice_time_tracking[member_id]['in_voice'] = True
        if 'join_time' in voice_time_tracking[member_id]:
            del voice_time_tracking[member_id]['join_time']
        logging.info("User joined AFK channel - marked as in voice but not tracked")
        await async_save_memory()
        return
    
    # Get trackable members
    trackable_members = _get_trackable_members(channel)
    
    # Handle muted+deafened users
    if is_muted_and_deafened(member):
        voice_time_tracking[member_id]['in_voice'] = True
        if 'join_time' in voice_time_tracking[member_id]:
            del voice_time_tracking[member_id]['join_time']
        logging.info(f"User {member.name} is muted AND deafened - not tracked")
    elif len(trackable_members) >= 2:
        voice_time_tracking[member_id]['join_time'] = current_time
        voice_time_tracking[member_id]['in_voice'] = True
        logging.info(f"Started tracking for {member.name} ({len(trackable_members)} trackable members)")
    else:
        voice_time_tracking[member_id]['in_voice'] = True
        if 'join_time' in voice_time_tracking[member_id]:
            del voice_time_tracking[member_id]['join_time']
        logging.info("User is alone in channel - not tracked")
    
    await async_save_memory()


async def _update_channel_tracking(channel: discord.VoiceChannel) -> None:
    """Update tracking status for all members in a specific channel."""
    if not channel:
        return
    
    current_time = datetime.now().timestamp()
    is_afk = channel.id in AFK_CHANNEL_IDS
    trackable_members = _get_trackable_members(channel) if not is_afk else []
    trackable_count = len(trackable_members)
    
    members_updated = 0
    for member in channel.members:
        if member.id in get_ignored_users():
            continue
        if _update_member_tracking(member, trackable_count, current_time, is_afk):
            members_updated += 1
    
    if members_updated > 0:
        await async_save_memory()


# ==============================================================================
# Event Handlers
# ==============================================================================

@bot.event
async def on_voice_state_update(
    member: discord.Member,
    before: discord.VoiceState,
    after: discord.VoiceState
) -> None:
    """Track time spent in voice channels."""
    # Ignore specified users
    if member.id in get_ignored_users():
        return
    
    current_time = datetime.now().timestamp()
    
    # Handle leaving voice channel
    if before and before.channel:
        await _handle_voice_leave(member, before.channel, current_time)
    
    # Handle joining voice channel
    if after and after.channel:
        is_new_join = not before.channel or before.channel != after.channel
        await _handle_voice_join(member, after.channel, current_time, is_new_join)
    
    # Update tracking for affected channels
    channels_to_update: set[discord.VoiceChannel] = set()
    if before and before.channel:
        channels_to_update.add(before.channel)
    if after and after.channel:
        channels_to_update.add(after.channel)
    
    for channel in channels_to_update:
        await _update_channel_tracking(channel)
        member_count = len([m for m in channel.members if m.id not in get_ignored_users()])
        logging.info(f"Voice channel update: Checked {member_count} members in '{channel.name}'")


async def update_tracking_for_specific_channel(channel: discord.VoiceChannel) -> None:
    """Update tracking status for all members in a specific voice channel."""
    await _update_channel_tracking(channel)


async def update_tracking_for_channel_changes() -> None:
    """Update tracking status for all voice channels in all guilds."""
    for guild in bot.guilds:
        for channel in guild.voice_channels:
            await _update_channel_tracking(channel)
    await async_save_memory()


async def check_and_respond(user_id: int, channel: discord.TextChannel) -> None:
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
async def on_message(message: discord.Message) -> None:
    if message.author == bot.user:
        return
    await check_and_respond(message.author.id, message.channel)
    await bot.process_commands(message)


@bot.event
async def on_reaction_add(reaction: discord.Reaction, user: discord.User) -> None:
    if user.bot:
        return
    await check_and_respond(user.id, reaction.message.channel)


@bot.event
async def on_reaction_remove(reaction: discord.Reaction, user: discord.User) -> None:
    if user.bot:
        return
    await check_and_respond(user.id, reaction.message.channel)


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent) -> None:
    if bot.user and payload.user_id != bot.user.id:
        channel = bot.get_channel(payload.channel_id)
        if channel:
            await check_and_respond(payload.user_id, channel)


@bot.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent) -> None:
    if bot.user and payload.user_id != bot.user.id:
        channel = bot.get_channel(payload.channel_id)
        if channel:
            await check_and_respond(payload.user_id, channel)

# Global flag to control shutdown
shutdown_requested: bool = False


async def graceful_shutdown() -> None:
    """Perform graceful shutdown of the bot."""
    global shutdown_requested
    shutdown_requested = True
    
    logging.info("Graceful shutdown initiated...")
    
    # Save current state
    await async_save_memory()
    
    # Stop periodic tasks
    if periodic_update.is_running():
        periodic_update.stop()
        logging.info("Stopped periodic update task")
    
    # Close the bot connection
    if not bot.is_closed():
        await bot.close()
        logging.info("Bot connection closed")
    
    logging.info("Graceful shutdown completed")


def signal_handler(signum: int, frame) -> None:
    """Handle shutdown signals."""
    logging.info(f"Received signal {signum}, initiating shutdown...")
    global shutdown_requested
    shutdown_requested = True
    sys.exit(0)


async def main() -> None:
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
