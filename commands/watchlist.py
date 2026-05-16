from __future__ import annotations

import discord
from discord.ext import commands
import json
import logging
from typing import Callable


def setup_watchlist(bot: commands.Bot, reload_watchlist_config_func: Callable[[], None]) -> None:
    reload_watchlist_config = reload_watchlist_config_func
    
    @bot.group(name='watchlist', invoke_without_command=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def watchlist(ctx: commands.Context) -> None:
        """Manage the watchlist for offline presence detection."""
        await ctx.send("Usage: `!watchlist add <user_id>`, `!watchlist remove <user_id>`, or `!watchlist list`")
    
    @watchlist.command(name='add')
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def watchlist_add(ctx: commands.Context, user_id: int) -> None:
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
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def watchlist_remove(ctx: commands.Context, user_id: int) -> None:
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
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def watchlist_list(ctx: commands.Context) -> None:
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
    
    @watchlist.group(name='onjoin', invoke_without_command=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def watchlist_onjoin(ctx: commands.Context) -> None:
        """Manage on-join messages for users."""
        await ctx.send("Usage: `!watchlist onjoin set <user_id> <message>`, `!watchlist onjoin remove <user_id>`, or `!watchlist onjoin list`")
    
    @watchlist_onjoin.command(name='set')
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def onjoin_set(ctx: commands.Context, user_id: int, *, message: str) -> None:
        """Set an on-join message for a user."""
        try:
            # Load current watchlist
            with open('watchlist.json', 'r') as f:
                data = json.load(f)
            
            # Initialize on_join_messages if not exists
            if 'on_join_messages' not in data:
                data['on_join_messages'] = {}
            
            # Set the message for this user
            data['on_join_messages'][str(user_id)] = message
            
            # Save updated watchlist
            with open('watchlist.json', 'w') as f:
                json.dump(data, f, indent=2)
            
            # Try to get user's display name
            user = ctx.guild.get_member(user_id)
            user_name = user.display_name if user else f"User ID {user_id}"
            
            await ctx.send(f"✅ Set on-join message for {user_name}: `{message}`")
            logging.info(f"Set on-join message for user {user_id} by {ctx.author}: {message}")
            
            # Reload the watchlist configuration
            reload_watchlist_config()
            
        except FileNotFoundError:
            await ctx.send("❌ Watchlist file not found. Please contact an administrator.")
        except json.JSONDecodeError:
            await ctx.send("❌ Error reading watchlist file. Please contact an administrator.")
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")
            logging.error(f"Error setting on-join message: {e}")
    
    @watchlist_onjoin.command(name='remove')
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def onjoin_remove(ctx: commands.Context, user_id: int) -> None:
        """Remove an on-join message for a user."""
        try:
            # Load current watchlist
            with open('watchlist.json', 'r') as f:
                data = json.load(f)
            
            on_join_messages = data.get('on_join_messages', {})
            user_id_str = str(user_id)
            
            if user_id_str not in on_join_messages:
                await ctx.send(f"User ID {user_id} does not have an on-join message set.")
                return
            
            # Remove the message
            del data['on_join_messages'][user_id_str]
            
            # Save updated watchlist
            with open('watchlist.json', 'w') as f:
                json.dump(data, f, indent=2)
            
            # Try to get user's display name
            user = ctx.guild.get_member(user_id)
            user_name = user.display_name if user else f"User ID {user_id}"
            
            await ctx.send(f"✅ Removed on-join message for {user_name}.")
            logging.info(f"Removed on-join message for user {user_id} by {ctx.author}")
            
            # Reload the watchlist configuration
            reload_watchlist_config()
            
        except FileNotFoundError:
            await ctx.send("❌ Watchlist file not found. Please contact an administrator.")
        except json.JSONDecodeError:
            await ctx.send("❌ Error reading watchlist file. Please contact an administrator.")
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")
            logging.error(f"Error removing on-join message: {e}")
    
    @watchlist_onjoin.command(name='list')
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def onjoin_list(ctx: commands.Context) -> None:
        """List all on-join messages."""
        try:
            # Load current watchlist
            with open('watchlist.json', 'r') as f:
                data = json.load(f)
            
            on_join_messages = data.get('on_join_messages', {})
            
            if not on_join_messages:
                await ctx.send("📝 No on-join messages configured.")
                return
            
            # Build list
            message_list = "📝 **On-Join Messages:**\n\n"
            for user_id_str, message in on_join_messages.items():
                user_id = int(user_id_str)
                user = ctx.guild.get_member(user_id)
                if user:
                    message_list += f"• **{user.display_name}** (ID: {user_id}): `{message}`\n"
                else:
                    message_list += f"• **Unknown User** (ID: {user_id}): `{message}`\n"
            
            await ctx.send(message_list)
            
        except FileNotFoundError:
            await ctx.send("❌ Watchlist file not found. Please contact an administrator.")
        except json.JSONDecodeError:
            await ctx.send("❌ Error reading watchlist file. Please contact an administrator.")
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")
            logging.error(f"Error listing on-join messages: {e}")
    
    return watchlist