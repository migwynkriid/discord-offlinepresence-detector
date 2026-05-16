from __future__ import annotations

import discord
from discord.ext import commands
import json
import logging
from typing import Callable


def setup_afkchannel(bot: commands.Bot, reload_afk_channels_func: Callable[[], None]) -> None:
    @bot.group(name='afkchannel', invoke_without_command=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def afkchannel(ctx: commands.Context) -> None:
        """Manage AFK channels where voice chat tracking is disabled."""
        await ctx.send("Usage: `!afkchannel add <channel_id>`, `!afkchannel remove <channel_id>`, or `!afkchannel list`")
    
    @afkchannel.command(name='add')
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def afkchannel_add(ctx: commands.Context, channel_id: int) -> None:
        """Add a voice channel to the AFK list (no tracking regardless of member count)."""
        try:
            # Verify the channel exists and is a voice channel
            channel = ctx.guild.get_channel(channel_id)
            if not channel:
                await ctx.send(f"❌ Channel with ID {channel_id} not found in this server.")
                return
            
            if not isinstance(channel, discord.VoiceChannel):
                await ctx.send(f"❌ Channel {channel.name} is not a voice channel.")
                return
            
            # Load current AFK channels list
            try:
                with open('afkchannels.json', 'r') as f:
                    data = json.load(f)
            except FileNotFoundError:
                data = {'afk_channel_ids': []}
            
            # Check if channel is already in the list
            if channel_id in data.get('afk_channel_ids', []):
                await ctx.send(f"Voice channel **{channel.name}** is already in the AFK list.")
                return
            
            # Add channel to the list
            if 'afk_channel_ids' not in data:
                data['afk_channel_ids'] = []
            data['afk_channel_ids'].append(channel_id)
            
            # Save updated AFK channels list
            with open('afkchannels.json', 'w') as f:
                json.dump(data, f, indent=2)
            
            await ctx.send(f"✅ Added voice channel **{channel.name}** to the AFK list. Voice activity will not be tracked in this channel.")
            logging.info(f"Added channel {channel_id} ({channel.name}) to AFK list by {ctx.author}")
            
            # Reload the AFK channels configuration
            reload_afk_channels_func()
            
        except ValueError:
            await ctx.send("❌ Invalid channel ID. Please provide a valid numeric channel ID.")
        except json.JSONDecodeError:
            await ctx.send("❌ Error reading AFK channels file. Please contact an administrator.")
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")
            logging.error(f"Error adding channel to AFK list: {e}")
    
    @afkchannel.command(name='remove')
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def afkchannel_remove(ctx: commands.Context, channel_id: int) -> None:
        """Remove a voice channel from the AFK list."""
        try:
            # Load current AFK channels list
            try:
                with open('afkchannels.json', 'r') as f:
                    data = json.load(f)
            except FileNotFoundError:
                await ctx.send("❌ No AFK channels configured.")
                return
            
            # Check if channel is in the list
            if channel_id not in data.get('afk_channel_ids', []):
                await ctx.send(f"Channel ID {channel_id} is not in the AFK list.")
                return
            
            # Remove channel from the list
            data['afk_channel_ids'].remove(channel_id)
            
            # Save updated AFK channels list
            with open('afkchannels.json', 'w') as f:
                json.dump(data, f, indent=2)
            
            # Try to get channel name for display
            channel = ctx.guild.get_channel(channel_id)
            channel_name = channel.name if channel else f"Channel ID {channel_id}"
            
            await ctx.send(f"✅ Removed voice channel **{channel_name}** from the AFK list. Voice activity tracking is now enabled.")
            logging.info(f"Removed channel {channel_id} from AFK list by {ctx.author}")
            
            # Reload the AFK channels configuration
            reload_afk_channels_func()
            
        except ValueError:
            await ctx.send("❌ Invalid channel ID. Please provide a valid numeric channel ID.")
        except json.JSONDecodeError:
            await ctx.send("❌ Error reading AFK channels file. Please contact an administrator.")
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")
            logging.error(f"Error removing channel from AFK list: {e}")
    
    @afkchannel.command(name='list')
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def afkchannel_list(ctx: commands.Context) -> None:
        """List all voice channels in the AFK list."""
        try:
            # Load current AFK channels list
            try:
                with open('afkchannels.json', 'r') as f:
                    data = json.load(f)
            except FileNotFoundError:
                await ctx.send("📝 No AFK channels configured. All voice channels will track activity based on member count.")
                return
            
            afk_channels = data.get('afk_channel_ids', [])
            
            if not afk_channels:
                await ctx.send("📝 No AFK channels configured. All voice channels will track activity based on member count.")
                return
            
            # Build list of AFK channels
            channel_list = "📝 **AFK Channels (No Tracking):**\n\n"
            for channel_id in afk_channels:
                channel = ctx.guild.get_channel(channel_id)
                if channel:
                    channel_list += f"🔇 **{channel.name}** (ID: {channel_id})\n"
                else:
                    channel_list += f"🔇 Unknown Channel (ID: {channel_id})\n"
            
            channel_list += "\n*Voice activity is not tracked in these channels regardless of member count.*"
            await ctx.send(channel_list)
            
        except json.JSONDecodeError:
            await ctx.send("❌ Error reading AFK channels file. Please contact an administrator.")
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")
            logging.error(f"Error listing AFK channels: {e}")
    
    return afkchannel