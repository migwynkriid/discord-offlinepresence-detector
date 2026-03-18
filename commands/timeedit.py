import discord
from discord.ext import commands
import json
import logging
import re

def setup_timeedit(bot, voice_time_tracking, update_voice_times, save_memory):
    def resolve_user(identifier):
        """
        Resolve a user identifier to a user ID.
        Accepts: user ID (numeric string) or Discord username/tag.
        Returns: (user_id, error_message) tuple. error_message is None on success.
        """
        # First, check if identifier is a numeric user ID
        if identifier.isdigit():
            return identifier, None
        
        # Otherwise, search by username (case-insensitive)
        identifier_lower = identifier.lower()
        matches = []
        
        for user_id, data in voice_time_tracking.items():
            username = data.get('username', '').lower()
            if username == identifier_lower or username.startswith(identifier_lower):
                matches.append((user_id, data.get('username', '')))
        
        if len(matches) == 0:
            return None, f"❌ No user found matching '{identifier}'. Try using their user ID instead."
        elif len(matches) == 1:
            return matches[0][0], None
        else:
            # Multiple matches - show them to the user
            match_list = '\n'.join([f"• {name} (ID: {uid})" for uid, name in matches[:10]])
            return None, f"❌ Multiple users match '{identifier}':\n{match_list}\nPlease use the user ID instead."
    
    def parse_time_string(time_str):
        """
        Parse time string like '1h 22m', '1h', '22m' and return total seconds.
        Returns None if parsing fails.
        """
        try:
            total_seconds = 0
            
            # Match hours (e.g., '1h', '2h')
            hours_match = re.search(r'(\d+)h', time_str, re.IGNORECASE)
            if hours_match:
                total_seconds += int(hours_match.group(1)) * 3600
            
            # Match minutes (e.g., '22m', '30m')
            minutes_match = re.search(r'(\d+)m', time_str, re.IGNORECASE)
            if minutes_match:
                total_seconds += int(minutes_match.group(1)) * 60
            
            # If no time was parsed, return None
            if total_seconds == 0 and not hours_match and not minutes_match:
                return None
                
            return total_seconds
        except Exception as e:
            logging.error(f"Error parsing time string '{time_str}': {e}")
            return None
    
    @bot.command(name='add')
    async def add_time(ctx, user_identifier: str, *time_parts):
        """
        Add time to a user's total time.
        Usage: !add USER_ID/USERNAME 1h 22m  OR  !add USER_ID/USERNAME 1h  OR  !add USER_ID/USERNAME 22m
        You can use either the user's ID or their Discord username.
        """
        # Join all time parts into a single string
        time_str = ' '.join(time_parts)
        
        if not time_str:
            await ctx.send("❌ Please specify time to add (e.g., `!add USER_ID 1h 22m` or `!add username 1h 22m`)")
            return
        
        # Parse the time string
        seconds_to_add = parse_time_string(time_str)
        
        if seconds_to_add is None or seconds_to_add == 0:
            await ctx.send("❌ Invalid time format. Use formats like: `1h`, `22m`, or `1h 22m`")
            return
        
        try:
            # Update all voice times first to ensure accurate current values
            update_voice_times()
            
            # Resolve user identifier to user ID
            user_id, error = resolve_user(user_identifier)
            if error:
                await ctx.send(error)
                return
            
            # Check if user exists in tracking
            if user_id not in voice_time_tracking:
                # Create new entry for this user
                voice_time_tracking[user_id] = {
                    'username': f'User_{user_id}',
                    'total_time': 0,
                    'in_voice': False
                }
                logging.info(f"Created new tracking entry for user {user_id}")
            
            # Add the time to total_time
            voice_time_tracking[user_id]['total_time'] += seconds_to_add
            
            # Save the changes
            save_memory()
            
            # Format the added time for display
            hours = int(seconds_to_add // 3600)
            minutes = int((seconds_to_add % 3600) // 60)
            time_display = []
            if hours > 0:
                time_display.append(f"{hours}h")
            if minutes > 0:
                time_display.append(f"{minutes}m")
            time_display_str = ' '.join(time_display)
            
            # Get total time for display
            total_seconds = voice_time_tracking[user_id]['total_time']
            total_hours = int(total_seconds // 3600)
            total_minutes = int((total_seconds % 3600) // 60)
            
            username = voice_time_tracking[user_id]['username']
            await ctx.send(f"✅ Added **{time_display_str}** to {username}'s time.\nNew total: **{total_hours}h {total_minutes}m**")
            logging.info(f"Added {seconds_to_add} seconds to user {user_id} (new total: {total_seconds})")
            
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")
            logging.error(f"Error adding time for user {user_id}: {e}")
    
    @bot.command(name='remove')
    async def remove_time(ctx, user_identifier: str, *time_parts):
        """
        Remove time from a user's total time.
        Usage: !remove USER_ID/USERNAME 1h 22m  OR  !remove USER_ID/USERNAME 1h  OR  !remove USER_ID/USERNAME 22m
        You can use either the user's ID or their Discord username.
        """
        # Join all time parts into a single string
        time_str = ' '.join(time_parts)
        
        if not time_str:
            await ctx.send("❌ Please specify time to remove (e.g., `!remove USER_ID 1h 22m` or `!remove username 1h 22m`)")
            return
        
        # Parse the time string
        seconds_to_remove = parse_time_string(time_str)
        
        if seconds_to_remove is None or seconds_to_remove == 0:
            await ctx.send("❌ Invalid time format. Use formats like: `1h`, `22m`, or `1h 22m`")
            return
        
        try:
            # Update all voice times first to ensure accurate current values
            update_voice_times()
            
            # Resolve user identifier to user ID
            user_id, error = resolve_user(user_identifier)
            if error:
                await ctx.send(error)
                return
            
            # Check if user exists in tracking
            if user_id not in voice_time_tracking:
                await ctx.send(f"❌ User '{user_identifier}' is not in the tracking system.")
                return
            
            # Remove the time from total_time (but don't go below 0)
            voice_time_tracking[user_id]['total_time'] = max(0, voice_time_tracking[user_id]['total_time'] - seconds_to_remove)
            
            # Save the changes
            save_memory()
            
            # Format the removed time for display
            hours = int(seconds_to_remove // 3600)
            minutes = int((seconds_to_remove % 3600) // 60)
            time_display = []
            if hours > 0:
                time_display.append(f"{hours}h")
            if minutes > 0:
                time_display.append(f"{minutes}m")
            time_display_str = ' '.join(time_display)
            
            # Get total time for display
            total_seconds = voice_time_tracking[user_id]['total_time']
            total_hours = int(total_seconds // 3600)
            total_minutes = int((total_seconds % 3600) // 60)
            
            username = voice_time_tracking[user_id]['username']
            await ctx.send(f"✅ Removed **{time_display_str}** from {username}'s time.\nNew total: **{total_hours}h {total_minutes}m**")
            logging.info(f"Removed {seconds_to_remove} seconds from user {user_id} (new total: {total_seconds})")
            
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")
            logging.error(f"Error removing time for user {user_id}: {e}")
