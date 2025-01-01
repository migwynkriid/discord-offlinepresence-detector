import os
import sys
import subprocess
import logging
from discord.ext import commands

def setup_update(bot, save_memory, periodic_update):
    @bot.command(name='update')
    async def update(ctx):
        """Update the bot from GitHub and restart. Only allowed for specific administrator."""
        if ctx.author.id != 220301180562046977:  # Check for specific admin ID
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
