import discord
from discord.ext import commands
import json
import logging

def setup_watchlist(bot):
    # Import the reload function from bot module
    from bot import reload_watchlist_config
    
    @bot.group(name='watchlist', invoke_without_command=True)
    async def watchlist(ctx):
        """Manage the watchlist for offline presence detection."""
        await ctx.send("Usage: `!watchlist add <user_id>`, `!watchlist remove <user_id>`, or `!watchlist list`")
    
    @watchlist.command(name='add')
    async def watchlist_add(ctx, user_id: int):
        """Add a user to the watchlist."""
        try:
            # Load current watchlist
            with open('watchlist.json', 'r') as f:
                data = json.load(f)
            
            # Check if user is already in the list
            if user_id in data.get('watched_user_ids', []):
                await ctx.send(f"User ID {user_id} is already in the watchlist.")
                return
            
            # Add user to the list
            if 'watched_user_ids' not in data:
                data['watched_user_ids'] = []
            data['watched_user_ids'].append(user_id)
            
            # Save updated watchlist
            with open('watchlist.json', 'w') as f:
                json.dump(data, f, indent=2)
            
            # Try to get user's display name
            user = ctx.guild.get_member(user_id)
            user_name = user.display_name if user else f"User ID {user_id}"
            
            await ctx.send(f"✅ Added {user_name} to the watchlist.")
            logging.info(f"Added user {user_id} to watchlist by {ctx.author}")
            
            # Reload the watchlist configuration
            reload_watchlist_config()
            
        except FileNotFoundError:
            await ctx.send("❌ Watchlist file not found. Please contact an administrator.")
        except json.JSONDecodeError:
            await ctx.send("❌ Error reading watchlist file. Please contact an administrator.")
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")
            logging.error(f"Error adding user to watchlist: {e}")
    
    @watchlist.command(name='remove')
    async def watchlist_remove(ctx, user_id: int):
        """Remove a user from the watchlist."""
        try:
            # Load current watchlist
            with open('watchlist.json', 'r') as f:
                data = json.load(f)
            
            # Check if user is in the list
            if user_id not in data.get('watched_user_ids', []):
                await ctx.send(f"User ID {user_id} is not in the watchlist.")
                return
            
            # Remove user from the list
            data['watched_user_ids'].remove(user_id)
            
            # Save updated watchlist
            with open('watchlist.json', 'w') as f:
                json.dump(data, f, indent=2)
            
            # Try to get user's display name
            user = ctx.guild.get_member(user_id)
            user_name = user.display_name if user else f"User ID {user_id}"
            
            await ctx.send(f"✅ Removed {user_name} from the watchlist.")
            logging.info(f"Removed user {user_id} from watchlist by {ctx.author}")
            
            # Reload the watchlist configuration
            reload_watchlist_config()
            
        except FileNotFoundError:
            await ctx.send("❌ Watchlist file not found. Please contact an administrator.")
        except json.JSONDecodeError:
            await ctx.send("❌ Error reading watchlist file. Please contact an administrator.")
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")
            logging.error(f"Error removing user from watchlist: {e}")
    
    @watchlist.command(name='list')
    async def watchlist_list(ctx):
        """List all users in the watchlist."""
        try:
            # Load current watchlist
            with open('watchlist.json', 'r') as f:
                data = json.load(f)
            
            watched_users = data.get('watched_user_ids', [])
            watch_everyone = data.get('watch_everyone', False)
            
            if watch_everyone:
                await ctx.send("🌍 **Watchlist Mode: Everyone**\nCurrently watching all users in the server.")
                return
            
            if not watched_users:
                await ctx.send("📝 The watchlist is currently empty.")
                return
            
            # Build list of watched users
            user_list = "📝 **Current Watchlist:**\n\n"
            for user_id in watched_users:
                user = ctx.guild.get_member(user_id)
                if user:
                    user_list += f"• {user.display_name} (ID: {user_id})\n"
                else:
                    user_list += f"• Unknown User (ID: {user_id})\n"
            
            await ctx.send(user_list)
            
        except FileNotFoundError:
            await ctx.send("❌ Watchlist file not found. Please contact an administrator.")
        except json.JSONDecodeError:
            await ctx.send("❌ Error reading watchlist file. Please contact an administrator.")
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")
            logging.error(f"Error listing watchlist: {e}")
    
    return watchlist