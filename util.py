import collections.abc
import re
import typing
import urllib.parse
from copy import copy
from io import StringIO
from random import choice

import discord
from discord import app_commands
from discord.ext import commands

_DISCORD_NICKNAME_ESCAPE_RE = re.compile(r'([\\*#_`>~|\[\]()-])')

if typing.TYPE_CHECKING:
    import patrick


class NoRelayException(Exception):
    ...


class BaseConversionError(ValueError):
    """
    Error to be used to forward custom exceptions from within :func:`baseconvert`.
    """


class RelayMember(discord.Member):
    """
    Subclass of discord.Member to signify that the member is a relay member.
    """

    @classmethod
    def _roles_from_name(cls, bot: patrick.Patrick, role_name: str) -> list[int]:
        # In Discord, the roles are called `Administrator` and `Moderator`,
        # while Chattore shows them as `Admin` and `Mod`. First we convert
        # the Chattore name to the Discord one.
        if role_name == "Admin":
            role_name = "Administrator"
        elif role_name == "Mod":
            role_name = "Moderator"

        # Boolean to indicate wether the user is Staff.
        staff = role_name in {"Administrator", "Moderator"}

        # Currently there is no other information we can grab from the Minecraft
        # format.
        roles: list[int] = [bot.member_roles[role_name]]

        if staff:
            roles.append(bot.member_roles["staff"])

        return roles

    @classmethod
    def from_member(cls, bot: patrick.Patrick, member: discord.User | discord.Member, nick: str, role_name: str) -> RelayMember:
        if isinstance(member, discord.User):
            raise TypeError("Expected instance of discord.Member in RelayMember.from_member, got discord.User instead.")

        self = copy(member)
        self.__class__ = RelayMember

        # Previous instance was a bot. Reset this for later usage.
        self.bot = False

        self._roles = discord.utils.SnowflakeList(cls._roles_from_name(bot, role_name))
        self.nick = nick

        # Once a Minecraft UUID - Discord ID Database is done, we can add more
        # here, or just grab the user instance with the ID.
        # TODO:
        #   For now we don't set the ID to anything new, which means stuff like reminders would ping the given Network Bot from now-on.
        #   Hopefully though a related PR (TO BE DONE) will be merged before that tough.

        return self # type: ignore[reportReturnType]


def mention(user_id: int) -> str:
    """
    Create a mention from a user-id. This is useful for cases where no
    :class:`discord.Member` can be created due to us only having a user-id,
    e.g. from a database query.
    """

    return f"<@{user_id}>"


def user_log_repr(user: discord.User | discord.Member) -> str:
    """
    Create a formatted string using the un-escaped nickname as well as the user
    id, so log messages are the same as in chattore.
    """

    return f"{user.display_name} ({user.id})"


def escape_nickname(name: str) -> str:
    """
    Escape all characters in a discord nickname so they don't convert to markdown.
    """

    return _DISCORD_NICKNAME_ESCAPE_RE.sub(r"\\\1", name)


def url_wrap(url: str, **params: str) -> str:
    """
    Create a wrapped URL, parsable e.g. by :func:`urllib.parse.unwrap`. Due to
    using keyword-argument syntax to pass the parameters, duplicate entries are
    not supported.
    """

    if not params:
        return f"<{url}>"

    return f"<{url}?{urllib.parse.urlencode(params, quote_via=urllib.parse.quote)}>"


def return_or_truncate(text: str, max_length: int) -> str:
    """Takes a string and truncates it to a maximum length, adding ellipsis if truncated.
    If the string is shorter than the maximum length, it returns the original string.

    Args:
        text (str): The string to be truncated.
        max_length (int): The maximum length of the string before truncation.

    Returns:
        str: The original string if it's shorter than max_length, otherwise the truncated string with ellipsis.
    """

    # TODO: CAP LEN AT 2k
    # max_length should never be smaller than / equal to 3 characters, but it's
    # better to be safe than sorry (and get weird text output).
    if len(text) <= max_length or max_length <= 3:
        return text

    return text[:max_length - 3] + "..."


def reformat_relay_chat(bot: patrick.Patrick, message: discord.Message, role_name: str, author_name: str, content: str) -> discord.Message:
    """
    Takes a Discord message and reformats it to be processed as a command by the bot.
    It also changes the author of the message to a RelayMember object.
    This is done to prevent the bot from trying to process commands as itself.
    Afterwards, the content is set to the content of the message sent in-game, and
    the message is returned.

    Args:
        bot (commands.Bot): The bot instance.
        message (discord.Message): The message to be reformatted.
        role_name (str): Name of the role of the user sending the message via the relay.
        author_name (str): Name of the user sending the message via the relay.
        content (str): Actual message content sent by the user.

    Returns:
        discord.Message: The reformatted message.
    """

    message.author = RelayMember.from_member(bot, message.author,
                                             author_name.replace("\\", ""),
                                             role_name)
    message.content = content
    return message


def get_raw_prefixes(bot: patrick.Patrick) -> list[str]:
    """
    Return all string prefixes the bot is listening to, sorted by decreasing
    lenght.

    String prefixes means that the message is not taken into consideration,
    which makes the :attr:`patrick.Patrick.command_prefix` unable to be a
    function.
    """

    if callable(bot.command_prefix):
        return []

    if isinstance(bot.command_prefix, str):
        return [bot.command_prefix]

    return sorted(bot.command_prefix, key=len, reverse=True)


def get_message_command_names(bot: patrick.Patrick, message: str) -> collections.abc.Generator[str]:
    """
    Take a message and extract all possible command names from it, e.g.:

        >>> bot.command_prefix = [",", ", ", ",command "]
        >>> msg = ",command hi"
        >>> for possible_name in get_message_command_names(bot, msg):
        ...     print(possible_name)
        ...
        hi
        command hi
        >>>
    """

    for prefix in get_raw_prefixes(bot):
        if message.startswith(prefix):
            yield message.removeprefix(prefix)


async def process_custom_command(bot, message: discord.Message) -> bool:
    """
    Take a message and check if it is a custom command. If it is, send a random response from the list of responses.
    If the command is not found, return False.

    Args:
        bot (commands.Bot): The bot instance.
        message (discord.Message): The message to check for a custom command.

    Returns:
        bool: True if the command was found and processed, False otherwise.
    """

    commands = bot.database.commands_cache
    for prefix in bot.command_prefix:
        if message.content.removeprefix(prefix) in commands:
            bot.logger.info(
                f"User {user_log_repr(message.author)} ran custom command '{message.content[1:]}'"
            )
            await message.channel.send(
                f"{escape_nickname(message.author.display_name)}: {choice(commands[message.content.removeprefix(prefix)])}"
            )
            await bot.database.add_command_history(
                # No need to escape name here, this is not sent immediately. Also, it might
                # cause problems with the current state of the DB.
                message.author.display_name, message.content.removeprefix(prefix)
            )
            return True
    return False


def load_automod_regexes(bot):
    """A setup function that loads the automod regexes from the config file.
    This runs a re.compile on each regex to create a compiled regex object for performance.

    Args:
        bot (commands.Bot): The bot instance.
    """

    bot.automod_regexes = [re.compile(regex, flags=re.IGNORECASE) for regex in bot.config["automod_regexes"]]


def find_automod_matches(bot, message: str) -> list[str]:
    """Checks a message against the automod regexes to see if it matches any of them.

    Args:
        bot (commands.Bot): The bot instance.
        message (str): An ingame message to check.

    Returns:
        list[str]: List of any matching regexes
    """

    return [regex.pattern for regex in bot.automod_regexes if regex.search(message)]


def is_staff():
    """A decorator that adds a commands.Check to a command to check if the user is a staff member.
    It checks if the user has the staff role in the config file. If they do, it returns True.
    If the user is a RelayMember, it returns False as well.
    If they don't, it raises a MissingPermissions error.
    """

    def predicate(ctx):
        if (
            not isinstance(ctx.author, discord.User)
            and not isinstance(ctx.author, RelayMember)
            and discord.utils.get(ctx.author.roles, id=ctx.bot.config["roles"]["staff"])
            is not None
        ):
            return True
        else:
            raise commands.MissingPermissions("You are not staff.")

    return commands.check(predicate)


def app_is_staff():
    """A decorator that adds a app_commands.Check to a command to check if the user is a staff member.
    It checks if the user has the staff role in the config file. If they do, it returns True.
    If they don't, it sends a message to the user saying they are not staff and returns False.
    """

    async def predicate(interaction: discord.Interaction):
        if (
            not isinstance(interaction.user, discord.User)
            and discord.utils.get(
                interaction.user.roles, id=interaction.client.config["roles"]["staff"]
            )
            is not None
        ):
            return True

        await interaction.response.send_message("You are not staff.", ephemeral=True)
        return False

    return app_commands.check(predicate)


def is_admin():
    """A decorator that adds a commands.Check to a command to check if the user is an admin.
    It checks if the user has the admin role in the config file. If they do, it returns True.
    If the user is a RelayMember, it returns False as well.
    If they don't, it raises a MissingPermissions error.
    """

    def predicate(ctx):
        if (
            not isinstance(ctx.author, discord.User)
            and not isinstance(ctx.author, RelayMember)
            and discord.utils.get(ctx.author.roles, id=ctx.bot.config["roles"]["admin"])
            is not None
        ):
            return True

        raise commands.MissingPermissions("You are not an admin.")

    return commands.check(predicate)


def app_is_admin():
    """A decorator that adds a app_commands.Check to a command to check if the user is an admin.
    It checks if the user has the admin role in the config file. If they do, it returns True.
    If they don't, it sends a message to the user saying they are not staff and returns False.
    """

    async def predicate(interaction: discord.Interaction):
        if (
            discord.utils.get(
                interaction.user.roles, id=interaction.client.config["roles"]["admin"]
            )
            is not None
        ):
            return True

        await interaction.response.send_message("You are not an admin.",
                                                ephemeral=True)
        return False

    return app_commands.check(predicate)


def is_discord_member():
    """A decorator that adds a commands.Check to a command to check if the user is a discord member.
    This allows you to stop certain commands from being run by relay members.
    """

    def predicate(ctx: commands.Context[patrick.Patrick]):
        if isinstance(ctx.author, RelayMember):
            raise commands.MissingPermissions("You are not a discord member.")

        return True

    return commands.check(predicate)


def split_list(a, n):
    """Split a list in n parts. The last part may be shorter than the others.

    Args:
        a (list): The list to split
        n (int): The amount of parts to split the list into

    Returns:
        list[list]: A list of n lists with the elements of the original list
    """

    k, m = divmod(len(a), n)
    return list(a[i * k + min(i, m) : (i + 1) * k + min(i + 1, m)] for i in range(n))


def baseconvert(number: str, base_from: int, base_to: int) -> str:
    """Convert a number from one base to another.

    Args:
        number (int): The number to convert.
        base_from (int): The base of the input number.
        base_to (int): The base to convert the number to.

    Returns:
        str: The converted number as a string.
    """

    characters = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz+/"
    if base_from > len(characters) or base_to > len(characters):
        raise BaseConversionError(f"Base must be between 2 and {len(characters)}.")
    if base_from < 2 or base_to < 2:
        raise BaseConversionError("Base must be at least 2.")

    if not all(char in characters for char in number):
        raise BaseConversionError("All characters of the given input must be in the range 0-9, A-Z and a-z or + and /. Underscores can be used to seperate parts of the number.")

    # Check for invalid cases with _ within the number.
    was_underscore: bool = False
    for idx, char in enumerate(number):
        if char == "_":
            if idx == 0:
                raise BaseConversionError("Number cannot start with underscore.")
            if idx == len(number) - 1:
                raise BaseConversionError("Number cannot end with underscore.")
            if was_underscore:
                raise BaseConversionError("Cannot use multiple consecutive underscores in a number.")
            was_underscore = True
        else:
            was_underscore = False

    # Remove all (valid) positions where _ is used.
    number = number.replace("_", "")

    # Convert from base_from to decimal
    # int can take base >= 2 and <= 36 (or 0)
    if base_from > 36:
        decimal_number = 0
        for index, char in enumerate(number[::-1]):
            decimal_number += characters.index(char) * base_from ** index

    else:
        decimal_number = int(str(number), base_from)

    # Convert from decimal to base_to
    if decimal_number == 0:
        return "0"

    # Shortcut for decimal. The number is already in base 10.
    if base_to == 10:
        return str(decimal_number)

    digits = []
    while decimal_number > 0:
        digits.append(characters[int(decimal_number % base_to)])
        decimal_number //= base_to

    return ''.join(str(digit) for digit in digits[::-1])  # Reverse the list and join as string


async def create_deletion_embed(
    staff: typing.Union[discord.Member, discord.User],
    reason: str,
    message: discord.Message,
) -> typing.Tuple[discord.Embed, typing.List[discord.File]]:
    """Creates an embed for a deletion action.

    Args:
        staff (discord.Member): The staff member who performed the deletion.
        reason (str): The reason for the deletion.
        message (discord.Message): The message that was deleted.

    Returns:
        discord.Embed: An embed containing the deletion information.
    """

    embed = discord.Embed(
        title="ORE Moderation Services",
        color=discord.Color.red(),
    )
    embed.set_thumbnail(url="https://i.imgflip.com/44o9ir.png")
    embed.add_field(name="Staff Member", value=staff.mention, inline=False)
    embed.add_field(name="User", value=message.author.mention, inline=True)
    embed.add_field(name="Display Name", value=escape_nickname(message.author.display_name), inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    if len(message.message_snapshots) > 0:
        embed.add_field(
            name="Forwarded Message Content",
            value=f"||{return_or_truncate(message.message_snapshots[0].content, 500)}||" if len(message.message_snapshots[0].content) > 0 else "No content",
            inline=False,
        )
        attachments = [await attachment.to_file(spoiler=True) for attachment in message.message_snapshots[0].attachments]
        # On long message, provide a .txt file with full content
        if len(message.message_snapshots[0].content) > 500:
            full_content_file = discord.File(
                fp=StringIO(message.message_snapshots[0].content),
                filename=f"message_{message.id}_full_content.txt",
                spoiler=True,
            )
            attachments.append(full_content_file)
    else:
        embed.add_field(name="Message Content", value=f"||{return_or_truncate(message.content, 500)}||" if len(message.content) > 0 else "No content", inline=False)
        attachments = [await attachment.to_file(spoiler=True) for attachment in message.attachments]
        # On long message, provide a .txt file with full content
        if len(message.content) > 500:
            full_content_file = discord.File(
                fp=StringIO(message.content),
                filename=f"message_{message.id}_full_content.txt",
                spoiler=True,
            )
            attachments.append(full_content_file)
    embed.add_field(name="Channel", value=message.channel.jump_url, inline=True)
    embed.add_field(name="Context", value=message.jump_url, inline=True)
    embed.set_footer(text=f"Message ID: {message.id}")
    embed.timestamp = discord.utils.utcnow()
    return embed, attachments


async def create_automod_embed(
    message: str,
    matches: list[str]
) -> discord.Embed:
    """Creates an embed for a deletion action.

    Args:
        message (str): The message that was flagged.
        matches (list[str]): The list of regex matches.

    Returns:
        discord.Embed: An embed containing the deletion information.
    """

    embed = discord.Embed(description=message, color=discord.Color.red())
    for match in matches:
        embed.add_field(name="Matches", value=f"`{match}`", inline=False)
    return embed


def get_all_command_names(bot: commands.Bot) -> typing.List[str]:
    """Get all commands registered in the bot.

    Args:
        bot (commands.Bot): The bot instance.

    Returns:
        typing.List[str]: A list of all commands.
    """

    command_names = []
    for command in bot.commands:
        if isinstance(command, commands.Group):
            command_names.extend([f"{command.name} {subcommand.name}" for subcommand in command.walk_commands()])
        else:
            command_names.append(command.name)
        # Add aliases if they exist
        if command.aliases:
            command_names.extend([alias for alias in command.aliases])
    return command_names


async def reply(ctx: commands.Context[patrick.Patrick], message=None, is_reply=False, is_silent=False, **kwargs):
    if message is None:
        message = ""
    target = ctx.reply if is_reply else ctx.send
    return await target(f"{escape_nickname(ctx.author.display_name)}: {message}", silent=is_silent, **kwargs)
