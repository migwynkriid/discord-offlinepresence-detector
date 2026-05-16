from __future__ import annotations

import discord
from discord.ext import commands
import json
import logging


def setup_listid(bot: commands.Bot) -> None:
    @bot.command(name='listid')
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def listid(ctx: commands.Context) -> None:
        """List all user IDs and usernames from memory.json (Manage Server permission required)."""
        # Check if the user has manage server permissions
        if not ctx.author.guild_permissions.manage_guild:
            await ctx.send("❌ This command requires 'Manage Server' permission.")
            return
        
        try:
            # Load memory.json
            with open('memory.json', 'r') as f:
                memory_data = json.load(f)
            
            if not memory_data:
                await ctx.send("📝 No user data found in memory.json")
                return
            
            # Build the user list
            user_list = "📝 **User IDs and Usernames from Memory:**\n\n"
            
            # Sort by username for better readability
            sorted_users = sorted(memory_data.items(), key=lambda x: x[1].get('username', 'Unknown'))
            
            for user_id, user_data in sorted_users:
                username = user_data.get('username', 'Unknown')
                total_time = user_data.get('total_time', 0)
                in_voice = user_data.get('in_voice', False)
                
                # Convert time to hours for display
                hours = total_time / 3600
                status = "🔊" if in_voice else "🔇"
                
                user_list += f"{status} **{username}** - ID: `{user_id}` ({hours:.1f}h)\n"
            
            # Split message if too long (Discord has a 2000 character limit)
            if len(user_list) > 1900:
                # Send in chunks
                lines = user_list.split('\n')
                current_chunk = lines[0] + '\n'  # Start with header
                
                for line in lines[1:]:
                    if len(current_chunk + line + '\n') > 1900:
                        await ctx.send(current_chunk)
                        current_chunk = line + '\n'
                    else:
                        current_chunk += line + '\n'
                
                if current_chunk.strip():
                    await ctx.send(current_chunk)
            else:
                await ctx.send(user_list)
            
            logging.info(f"User {ctx.author} with manage server permissions requested user ID list")
            
        except FileNotFoundError:
            await ctx.send("❌ Memory file not found. No user data available.")
        except json.JSONDecodeError:
            await ctx.send("❌ Error reading memory file. Data may be corrupted.")
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")
            logging.error(f"Error in listid command: {e}")
    
    return listid