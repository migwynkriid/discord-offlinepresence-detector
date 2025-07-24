import discord
from discord.ext import commands
import os
import logging
from datetime import datetime

def setup_backup(bot):
    @bot.command(name='backup')
    async def backup(ctx):
        """Upload the latest backup file from the backup folder (Manage Server permission required)."""
        # Check if the user has manage server permissions
        if not ctx.author.guild_permissions.manage_guild:
            await ctx.send("❌ This command requires 'Manage Server' permission.")
            return
        
        try:
            backup_folder = 'backup'
            
            # Check if backup folder exists
            if not os.path.exists(backup_folder):
                await ctx.send("❌ Backup folder not found.")
                return
            
            # Get all backup files
            backup_files = [f for f in os.listdir(backup_folder) if f.startswith('memory-') and f.endswith('.json')]
            
            if not backup_files:
                await ctx.send("❌ No backup files found in the backup folder.")
                return
            
            # Sort files by name (which includes timestamp) to get the latest
            backup_files.sort(reverse=True)
            latest_backup = backup_files[0]
            latest_backup_path = os.path.join(backup_folder, latest_backup)
            
            # Check file size (Discord has a file size limit)
            file_size = os.path.getsize(latest_backup_path)
            if file_size > 8 * 1024 * 1024:  # 8MB limit for non-nitro users
                await ctx.send(f"❌ Backup file is too large ({file_size / 1024 / 1024:.1f}MB). Discord file limit is 8MB.")
                return
            
            # Extract timestamp from filename for display
            timestamp_part = latest_backup.replace('memory-', '').replace('.json', '')
            try:
                # Parse the timestamp (format: YYYY-MM-DD-HHMM)
                date_part, time_part = timestamp_part.split('-')[0:3], timestamp_part.split('-')[3]
                formatted_date = f"{date_part[0]}-{date_part[1]}-{date_part[2]}"
                formatted_time = f"{time_part[:2]}:{time_part[2:]}"
                display_timestamp = f"{formatted_date} {formatted_time}"
            except:
                display_timestamp = timestamp_part
            
            # Create Discord file object and send it
            with open(latest_backup_path, 'rb') as f:
                discord_file = discord.File(f, filename=latest_backup)
            
            await ctx.send(file=discord_file)
            
            logging.info(f"User {ctx.author} downloaded backup file: {latest_backup}")
            
        except FileNotFoundError:
            await ctx.send("❌ Backup file not found or has been moved.")
        except PermissionError:
            await ctx.send("❌ Permission denied accessing backup file.")
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")
            logging.error(f"Error in backup command: {e}")
    
    return backup