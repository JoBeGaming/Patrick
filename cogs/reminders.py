import collections.abc
import typing
from datetime import datetime, timedelta

import discord
from discord.ext import commands, tasks
from discord.utils import format_dt

from paginator import EmbedPaginatorSession
from timeutil import UserFriendlyTime
from util import escape_nickname, is_discord_member, mention, return_or_truncate

if typing.TYPE_CHECKING:
    import patrick  # noqa: TC004


type DiscordTimeFlag =  typing.Literal["t", "T", "d", "D", "f", "F", "R"]


DEFAULT_COLOR: discord.Color = discord.Color.blue()


class Reminders(commands.Cog):
    def __init__(self, bot: patrick.Patrick):
        self.bot = bot
        self.check_reminders.start()

    @is_discord_member()
    @commands.command(name='remindme', aliases=['reminder', 'remind'])
    async def remind_me(self, ctx: commands.Context[patrick.Patrick], *, time: UserFriendlyTime):
        """
        Set a reminder.
        """

        message = time.arg
        dt: datetime = time.dt # type: ignore
        await self.bot.database.add_reminder(
            user_id=ctx.author.id,
            channel_id=ctx.channel.id,
            message=message,
            timestamp=dt
        )

        msg = f"{ctx.author.mention}: I'll remind you at {dt.strftime('%Y-%m-%d %H:%M:%S')} "\
              f"UTC ({format_dt(dt, style="R")})"

        if message:
            # Picked 100 after a lot of long and very illegal testing. Sorry Eith.
            msg += f" with the message: {return_or_truncate(message, 100)}"
        await ctx.reply(msg)

    async def _field_values(self, reminders: collections.abc.Iterable[tuple[str, int, datetime]], /) -> collections.abc.AsyncGenerator[tuple[int, dict[str, str]]]:
        for index, (message, _, timestamp) in enumerate(reminders):
            yield index, {"name": f"Reminder at {timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
                          "value": f"Message: {message or '-'}"}

    def _make_embed(self, ctx: commands.Context[patrick.Patrick], color: discord.Color = DEFAULT_COLOR, /) -> discord.Embed:
        return discord.Embed(title=f"{escape_nickname(ctx.author.display_name)}'s Reminders",
                             color=color)

    def _add_field(self, embed: discord.Embed, kwds: dict[str, str], /) -> None:
        embed.add_field(**kwds,
                        inline=False)

    @is_discord_member()
    @commands.command(name='reminders', aliases=['myreminders'])
    async def my_reminders(self, ctx: commands.Context[patrick.Patrick]):
        """
        List all reminders set by the user.
        """

        reminders = await self.bot.database.get_reminders(ctx.author.id)
        if not reminders:
            return await ctx.reply(f"{escape_nickname(ctx.author.display_name)}: You have no reminders set.")

        if len(reminders) > 5:
            embeds = [self._make_embed(ctx) for _ in range((len(reminders) - 1) // 5 + 1)]
            async for index, kwds in self._field_values(reminders):
                self._add_field(embeds[index // 5], kwds)

            paginator = EmbedPaginatorSession(ctx, *embeds)
            return await paginator.run()

        embed = self._make_embed(ctx)
        async for index, kwds in self._field_values(reminders):
            self._add_field(embed, kwds)

        await ctx.reply(embed=embed)

    @tasks.loop(seconds=60)
    async def check_reminders(self):
        """
        Check for reminders that need to be sent.
        """

        for (user_id, channel_id, message) in await self.bot.database.pop_expired_reminders():
            channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
            if not message:
                message = "You asked me to remind you!"

            try:
                if not isinstance(channel, (discord.abc.PrivateChannel,
                                            discord.channel.VoiceChannel,
                                            discord.channel.ForumChannel,
                                            discord.channel.StageChannel,
                                            discord.CategoryChannel)):
                    await channel.send(f"{mention(user_id)}: {message}")

            except discord.Forbidden:
                # If the bot cannot send messages to the channel, skip it. Due
                # to the `isinstance` done before the `channel.send`, this should
                # not be needed though, but you can never be too sure.
                continue

    @check_reminders.error
    async def check_reminders_error(self, error: BaseException) -> None:
        """
        Handle errors in the check_reminders task.
        """

        self.bot.logger.error(f"Error in check_reminders task: {error}")
        try:
            self.check_reminders.cancel()  # Stop the task to prevent further errors
        except Exception as e:
            self.bot.logger.error(f"Failed to cancel check_reminders task: {e}")
        self.check_reminders.start()  # Restart the task


async def setup(bot: patrick.Patrick) -> None:
    """
    Setup of this cog.
    """

    await bot.add_cog(Reminders(bot))
