import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from typing_extensions import Self

from util import is_discord_member
from timeutil import UserFriendlyTime

class Reminders(commands.Cog):
    def __init__(self: Self, bot) -> None:
        self.bot = bot
        self.check_reminders.start()

    @is_discord_member()
    @commands.command(name='remindme', aliases=['reminder', 'remind', 'set_reminder'])
    async def remind_me(self: Self, ctx, *, time: UserFriendlyTime) -> None:
        """Set a reminder."""
        message = time.arg
        await self.bot.database.add_reminder(
            user_id=ctx.author.id,
            channel_id=ctx.channel.id,
            message=message,
            timestamp=time.dt
        )
        await ctx.reply(f"{ctx.author.mention}: I will remind you at {time.dt.strftime('%Y-%m-%d %H:%M:%S')} UTC with the message: {message}")

    @is_discord_member()
    @commands.command(name='reminders', aliases=['myreminders'])
    async def my_reminders(self: Self, ctx) -> None:
        """List all reminders set by the user."""
        reminders = await self.bot.database.get_reminders(ctx.author.id)
        if not reminders:
            return await ctx.reply(f"{ctx.author.display_name}: You have no reminders set.")
        elif len(reminders) < 25:
            embed = discord.Embed(title=f"{ctx.author.display_name}'s Reminders", color=discord.Color.blue())
            for message, _, timestamp in reminders:
                embed.add_field(
                    name=f"Reminder at {timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
                    value=f"Message: {message}",
                    inline=False
                )
            await ctx.reply(embed=embed)

    @tasks.loop(seconds=60)
    async def check_reminders(self: Self):
        """Check for reminders that need to be sent."""
        reminders = await self.bot.database.pop_expired_reminders()
        for reminder in reminders:
            user_id, channel_id, message = reminder
            channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
            try:
                await channel.send(f"<@{user_id}>: {message}")
            except discord.Forbidden:
                # If the bot cannot send messages to the channel, skip it
                continue

async def setup(bot: discord.ext.commands.Bot) -> None:
    await bot.add_cog(Reminders(bot))