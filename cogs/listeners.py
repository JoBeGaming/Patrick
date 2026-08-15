import discord
from discord.ext import commands
from random import choice
import asyncio

class Listeners(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        greeting: str = choice(self.bot.config["greetings"])
        channel: discord.abc.Messageable = member.guild.get_channel(self.bot.config["channels"]["welcome"])
        await channel.send(greeting.format(user=member.mention))

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread):
        if thread.parent_id in self.bot.config["autosub_forums"]:
            role = await thread.guild.fetch_role(self.bot.config["roles"]["staff"])
            to_send = " ".join(member.mention for member in role.members)
            try:
                await thread.send(to_send, silent=True, delete_after=1)
            except discord.Forbidden as e:
                if e.code == 40058:
                    # Sometimes, discord sends the thread create event too early, causing a race condition. We can wait a bit and try again.
                    await asyncio.sleep(2)
                    await thread.send(to_send, silent=True, delete_after=1)

async def setup(bot: commands.Bot):
    await bot.add_cog(Listeners(bot))