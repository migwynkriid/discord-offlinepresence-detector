import discord
from discord.ext import commands
import json
import logging

def setup_ignore(bot, reload_ignored_users_func):
    # Use the reload function passed as parameter to avoid circular imports
    
    @bot.group(name='ignore', invoke_without_command=True)
    async def ignore(ctx):
        """Manage the ignore list for voice chat tracking."""
        await ctx.send("Usage: `!ignore add <user_id>`, `!ignore remove <user_id>`, or `!ignore list`")
    
    @ignore.command(name='add')
    async def ignore_add(ctx, user_id: int):
        """Add a user to the ignore list."""
        try:
            # Load current ignore list
            with open('ignore.json', 'r') as f:
                data = json.load(f)
            
            # Check if user is already in the list
            if user_id in data.get('ignored_user_ids', []):
                await ctx.send(f"User ID {user_id} is already in the ignore list.")
                return
            
            # Add user to the list
            if 'ignored_user_ids' not in data:
                data['ignored_user_ids'] = []
            data['ignored_user_ids'].append(user_id)
            
            # Save updated ignore list
            with open('ignore.json', 'w') as f:
                json.dump(data, f, indent=2)
            
            # Try to get user's display name
            user = ctx.guild.get_member(user_id)
            user_name = user.display_name if user else f"User ID {user_id}"
            
            await ctx.send(f"✅ Added {user_name} to the ignore list. They will be excluded from the leaderboard.")
            logging.info(f"Added user {user_id} to ignore list by {ctx.author}")
            
            # Reload the ignore configuration
            reload_ignored_users_func()
            
        except FileNotFoundError:
            await ctx.send("❌ Ignore file not found. Please contact an administrator.")
        except json.JSONDecodeError:
            await ctx.send("❌ Error reading ignore file. Please contact an administrator.")
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")
            logging.error(f"Error adding user to ignore list: {e}")
    
    @ignore.command(name='remove')
    async def ignore_remove(ctx, user_id: int):
        """Remove a user from the ignore list."""
        try:
            # Load current ignore list
            with open('ignore.json', 'r') as f:
                data = json.load(f)
            
            # Check if user is in the list
            if user_id not in data.get('ignored_user_ids', []):
                await ctx.send(f"User ID {user_id} is not in the ignore list.")
                return
            
            # Remove user from the list
            data['ignored_user_ids'].remove(user_id)
            
            # Save updated ignore list
            with open('ignore.json', 'w') as f:
                json.dump(data, f, indent=2)
            
            # Try to get user's display name
            user = ctx.guild.get_member(user_id)
            user_name = user.display_name if user else f"User ID {user_id}"
            
            await ctx.send(f"✅ Removed {user_name} from the ignore list. They will now appear in the leaderboard.")
            logging.info(f"Removed user {user_id} from ignore list by {ctx.author}")
            
            # Reload the ignore configuration
            reload_ignored_users_func()
            
        except FileNotFoundError:
            await ctx.send("❌ Ignore file not found. Please contact an administrator.")
        except json.JSONDecodeError:
            await ctx.send("❌ Error reading ignore file. Please contact an administrator.")
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")
            logging.error(f"Error removing user from ignore list: {e}")
    
    @ignore.command(name='list')
    async def ignore_list(ctx):
        """List all users in the ignore list."""
        try:
            # Load current ignore list
            with open('ignore.json', 'r') as f:
                data = json.load(f)
            
            ignored_users = data.get('ignored_user_ids', [])
            
            if not ignored_users:
                await ctx.send("📝 The ignore list is currently empty. All users will appear in the leaderboard.")
                return
            
            # Build list of ignored users
            user_list = "📝 **Current Ignore List:**\n\n"
            for user_id in ignored_users:
                user = ctx.guild.get_member(user_id)
                if user:
                    user_list += f"• {user.display_name} (ID: {user_id})\n"
                else:
                    user_list += f"• Unknown User (ID: {user_id})\n"
            
            user_list += "\n*These users are excluded from the voice chat leaderboard.*"
            await ctx.send(user_list)
            
        except FileNotFoundError:
            await ctx.send("❌ Ignore file not found. Please contact an administrator.")
        except json.JSONDecodeError:
            await ctx.send("❌ Error reading ignore file. Please contact an administrator.")
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")
            logging.error(f"Error listing ignore list: {e}")
    
    return ignore
