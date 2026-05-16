from __future__ import annotations

import os
import sys
import subprocess
import logging
from discord.ext import commands, tasks
from typing import Callable


def setup_restart(
    bot: commands.Bot,
    save_memory: Callable[[], None],
    periodic_update: tasks.Loop,
    update_voice_times: Callable[[], None]
) -> None:
    @bot.command(name='restart')
    @commands.cooldown(1, 60, commands.BucketType.guild)
    async def restart(ctx: commands.Context) -> None:
        """Restart the bot. Only allowed for bot administrators."""
        # Get admin ID from environment variable, with fallback
        admin_id = int(os.getenv('BOT_ADMIN_ID', '0'))
        if admin_id == 0 or ctx.author.id != admin_id:
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
