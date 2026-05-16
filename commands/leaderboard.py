from __future__ import annotations

import discord
from discord.ext import commands
from datetime import datetime
import logging
from typing import Callable


def setup_leaderboard(
    bot: commands.Bot,
    voice_time_tracking: dict,
    get_ignored_users_func: Callable[[], list[int]],
    update_voice_times: Callable[[], None]
) -> None:
    @bot.command(name='leaderboard')
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def leaderboard(ctx: commands.Context) -> None:
        """Display the voice chat time leaderboard."""
        # Get current ignored users list
        current_ignored_users = get_ignored_users_func()
        
        logging.info(f"Leaderboard: Ignored users list: {current_ignored_users}")
        logging.info(f"Leaderboard: Total users in tracking: {len(voice_time_tracking)}")
        
        current_time = datetime.now().timestamp()
        
        # Update times for all active users before displaying
        update_voice_times()
        
        # Filter out ignored users and sort by total time (highest to lowest)
        sorted_users = sorted(
            [(user_id, time_data) for user_id, time_data in voice_time_tracking.items() 
             if int(user_id) not in current_ignored_users],
            key=lambda x: x[1]['total_time'],
            reverse=True
        )
        
        filtered_count = len(voice_time_tracking) - len(sorted_users)
        logging.info(f"Leaderboard: Filtered out {filtered_count} users, showing {len(sorted_users)} users")
        
        # Log which users are being shown
        logging.info(f"Leaderboard users: {[(uid, data.get('username')) for uid, data in sorted_users[:10]]}")
        
        # Create simple text leaderboard
        leaderboard_text = "**Voice Chat Time Leaderboard**\n\n"
        
        # Add user entries to text
        for rank, (user_id, time_data) in enumerate(sorted_users, 1):
            # Calculate total time including current session if user is in voice
            total_seconds = time_data['total_time']
            if time_data.get('in_voice', False) and 'join_time' in time_data:
                current_session = current_time - time_data['join_time']
                total_seconds += current_session
            
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            # Show different status based on tracking state
            if time_data.get('in_voice', False):
                if 'join_time' in time_data:
                    status = "🔊"  # In voice and being tracked (with others)
                else:
                    status = "🔇"  # In voice but not tracked (alone)
            else:
                status = "💤"  # Not in voice
            user = time_data['username']
            
            # Add user line to leaderboard
            time_text = f"{hours}h {minutes}m"
            leaderboard_text += f"{rank}. {status} **{user}** - {time_text}\n"
        
        await ctx.send(leaderboard_text)
    
    return leaderboard
