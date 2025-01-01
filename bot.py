import os
import sys
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import subprocess
from datetime import datetime, timedelta
import json
import logging
import pytz  # Add pytz for timezone handling

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

# List of user IDs to ignore in voice tracking
IGNORED_USER_IDS = [506216844856786974, 506924316403957760]

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
    
    # Update time for users currently in voice channels
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

def reset_counters():
    """Reset all users' total_time to 0"""
    logging.info("Resetting daily voice time counters...")
    for user_id in voice_time_tracking:
        voice_time_tracking[user_id]['total_time'] = 0
    save_memory()

@tasks.loop(minutes=10)
async def periodic_update():
    """Task that runs every 10 minutes to update voice times and check for daily reset."""
    logging.info("Updating voice chat times...")
    update_voice_times()
    
    if should_reset():
        reset_counters()
        # Log the reset
        logging.info("Daily voice time counters have been reset")

@bot.event
async def on_ready():
    """Event handler for when the bot is ready and connected to Discord."""
    logging.info(f'{bot.user} has connected to Discord!')
    logging.info(f'Bot is in {len(bot.guilds)} guilds')
    
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

@bot.event
async def on_voice_state_update(member, before, after):
    """Track time spent in voice channels."""
    # Ignore specified users
    if member.id in IGNORED_USER_IDS:
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

@bot.command(name='leaderboard')
async def leaderboard(ctx):
    """Display the voice chat time leaderboard."""
    current_time = datetime.now().timestamp()
    
    # Update times for all active users before displaying
    update_voice_times()
    
    # Filter out ignored users and sort by total time (highest to lowest)
    sorted_users = sorted(
        [(user_id, time_data) for user_id, time_data in voice_time_tracking.items() 
         if int(user_id) not in IGNORED_USER_IDS],
        key=lambda x: x[1]['total_time'],
        reverse=True
    )
    
    # Create leaderboard message
    leaderboard_text = "Voice Chat Time Leaderboard\n-------------------------\n"
    for rank, (user_id, time_data) in enumerate(sorted_users, 1):
        # Calculate total time including current session if user is in voice
        total_seconds = time_data['total_time']
        if time_data.get('in_voice', False) and 'join_time' in time_data:
            current_session = current_time - time_data['join_time']
            total_seconds += current_session
        
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        status = "🔊" if time_data.get('in_voice', False) else "💤"
        user = time_data['username']
        
        leaderboard_text += f"{status} {user}: {hours} hours and {minutes} minutes\n"
    
    await ctx.send(f"```\n{leaderboard_text}\n```")
    await ctx.send(file=discord.File('memory.json'))

@bot.command(name='restart')
async def restart(ctx):
    """Restart the bot. Only allowed for specific administrator."""
    if ctx.author.id != 220301180562046977:  # Check for specific admin ID
        await ctx.send("You don't have permission to use this command.")
        return
        
    await ctx.send("Restarting bot...")
    logging.info("Restart command received. Restarting bot...")
    save_memory()
    periodic_update.stop()
    
    script_path = os.path.abspath(sys.argv[0])
    subprocess.Popen([sys.executable, script_path])
    await bot.close()
    sys.exit()

async def check_and_respond(user_id, channel):
    """Common function to check user status and respond if needed."""
    member = channel.guild.get_member(user_id)
    if member and member.id in [226711001469288448]:
        current_time = datetime.now()
        last_time = last_message_time.get(member.id)
        
        if last_time is None or (current_time - last_time) > timedelta(days=1):
            if member.status in [discord.Status.offline, discord.Status.invisible]:
                await channel.send(f"<@{member.id}> ka dialas offline budala")
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
    if payload.user_id != bot.user.id:
        channel = bot.get_channel(payload.channel_id)
        await check_and_respond(payload.user_id, channel)

@bot.event
async def on_raw_reaction_remove(payload):
    if payload.user_id != bot.user.id:
        channel = bot.get_channel(payload.channel_id)
        await check_and_respond(payload.user_id, channel)

# Get the token from environment variables
TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    raise ValueError("No Discord token found. Make sure to set DISCORD_TOKEN in your .env file")

# Run the bot
bot.run(TOKEN)
