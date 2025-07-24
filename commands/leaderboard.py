import discord
from discord.ext import commands
from datetime import datetime

def setup_leaderboard(bot, voice_time_tracking, IGNORED_USER_IDS, update_voice_times):
    @bot.command(name='leaderboard')
    async def leaderboard(ctx):
        """Display the voice chat time leaderboard."""
        # Import current ignored users list
        from bot import IGNORED_USER_IDS as current_ignored_users
        
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
            status = "🔊" if time_data.get('in_voice', False) else "💤"
            user = time_data['username']
            
            # Add user line to leaderboard
            time_text = f"{hours}h {minutes}m"
            leaderboard_text += f"{rank}. {status} **{user}** - {time_text}\n"
        
        await ctx.send(leaderboard_text)
    
    return leaderboard
