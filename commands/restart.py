import os
import sys
import subprocess
import logging
from discord.ext import commands

def setup_restart(bot, save_memory, periodic_update, update_voice_times):
    @bot.command(name='restart')
    async def restart(ctx):
        """Restart the bot. Only allowed for specific administrator."""
        if ctx.author.id != 220301180562046977:  # Check for specific admin ID
            await ctx.send("You don't have permission to use this command.")
            return
            
        await ctx.send("Restarting bot...")
        logging.info("Restart command received. Restarting bot...")
        save_memory()
        periodic_update.stop()
        update_voice_times()  # Update all active voice times before saving
        save_memory()
        
        script_path = os.path.abspath(sys.argv[0])
        subprocess.Popen([sys.executable, script_path])
        try:
            await bot.close()
        except:
            pass
    
    return restart
