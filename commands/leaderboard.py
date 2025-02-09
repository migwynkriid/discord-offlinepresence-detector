import discord
from discord.ext import commands
from datetime import datetime

def setup_leaderboard(bot, voice_time_tracking, IGNORED_USER_IDS, update_voice_times):
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
        
        # Create embed
        embed = discord.Embed(
            title="Voice Chat Time Leaderboard",
            color=discord.Color.blue()
        )
        
        # Add user entries to embed
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
            
            # Try to get the member object to get their avatar
            member = ctx.guild.get_member(int(user_id))
            avatar_url = member.display_avatar.url if member else None
            
            # Add field for each user
            time_text = f"{hours} hours and {minutes} minutes"
            embed.add_field(
                name=f"{status} {user}",
                value=time_text,
                inline=False
            )
            
            # Set the user's avatar as thumbnail for first place
            if rank == 1 and avatar_url:
                embed.set_thumbnail(url=avatar_url)
        
        await ctx.send(embed=embed)
    
    return leaderboard
