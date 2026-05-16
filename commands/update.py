from __future__ import annotations

import os
import sys
import subprocess
import logging
from discord.ext import commands, tasks
from typing import Callable


def setup_update(
    bot: commands.Bot,
    save_memory: Callable[[], None],
    periodic_update: tasks.Loop,
    update_voice_times: Callable[[], None]
) -> None:
    @bot.command(name='update')
    @commands.cooldown(1, 60, commands.BucketType.guild)
    async def update(ctx: commands.Context) -> None:
        """Update the bot from GitHub and restart. Only allowed for bot administrators."""
        # Get admin ID from environment variable, with fallback
        admin_id = int(os.getenv('BOT_ADMIN_ID', '0'))
        if admin_id == 0 or ctx.author.id != admin_id:
            await ctx.send("You don't have permission to use this command.")
            return
            
        await ctx.send("Pulling latest changes from GitHub...")
        logging.info("Update command received. Pulling from GitHub...")
        
        try:
            # Run git pull with force flags
            process = subprocess.Popen(['git', 'fetch', 'origin', 'master'],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
            output, error = process.communicate()
            
            if process.returncode == 0:
                reset_process = subprocess.Popen(['git', 'reset', '--hard', 'origin/master'],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
                output, error = reset_process.communicate()
                
                if reset_process.returncode == 0:
                    await ctx.send("Update successful! Restarting bot...")
                    logging.info("Git pull successful. Restarting bot...")
                    
                    # Save state and stop periodic updates
                    save_memory()
                    periodic_update.stop()
                    update_voice_times()  # Update all active voice times before saving
                    save_memory()
                    
                    # Restart the bot
                    script_path = os.path.abspath(sys.argv[0])
                    subprocess.Popen([sys.executable, script_path])
                    try:
                        await bot.close()
                    except:
                        pass
                else:
                    error_msg = error.decode('utf-8') if error else 'Unknown error'
                    await ctx.send(f"Failed to update: {error_msg}")
                    logging.error(f"Git reset failed: {error_msg}")
            else:
                error_msg = error.decode('utf-8') if error else 'Unknown error'
                await ctx.send(f"Failed to update: {error_msg}")
                logging.error(f"Git fetch failed: {error_msg}")
                
        except Exception as e:
            await ctx.send(f"An error occurred during update: {str(e)}")
            logging.error(f"Update error: {str(e)}")
    
    return update
