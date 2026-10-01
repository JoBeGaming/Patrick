import collections.abc
import logging
import re
import typing
from os import getenv, listdir
from pathlib import Path

import discord
import yaml
from aiohttp import ClientSession
from discord.ext import commands

from dotenv import load_dotenv

import database
from logger import StreamLogFormatter, setup_logger
from util import (
    RelayMember,
    create_automod_embed,
    escape_nickname,
    find_automod_matches,
    is_admin,
    load_automod_regexes,
    process_custom_command,
    reformat_relay_chat,
    reply,
    split_list,
    user_log_repr,
    get_message_command_names
)

load_dotenv(Path(__file__).parent / ".env")
TOKEN: str = getenv("TOKEN")


def load_config():
    with open(Path(__file__).parent / "config.yaml", "r") as source:
        return yaml.safe_load(source)


class PatrickHelp(commands.HelpCommand):
    """A custom implementation of the HelpCommand class to provide a custom help command.
    This class is used to format the help message and send it to the user.
    It is a base feature of the discord.py library.
    """

    def __init__(self):
        super().__init__()

    async def get_commands_mapping(self) -> tuple:
        """Retrieves a tuple of dictionaries containing the commands and custom commands.

        Returns:
            tuple: A 2-tuple containing two dictionaries:
                - The first dictionary contains the commands and their help message and signature.
                - The second dictionary contains the custom commands and their messages.
        """
        commands_ = {
            command.name: (
                command.signature,
                command.help if command.help is not None else "",
            )
            for command in self.context.bot.commands
        }
        custom_commands = self.context.bot.database.commands_cache
        return commands_, custom_commands

    def format_table(
        self, commands_mapping: dict, custom_commands_mapping: dict
    ) -> str:
        """Formats a table of commands and custom commands into a string.

        Args:
            commands_mapping (dict): The disctionary containing the commands and their help message and signature.
            custom_commands_mapping (dict): The dictionary containing the custom commands and their messages.

        Returns:
            str: A formatted string containing the commands and custom commands in a table format.
        """
        maxlen_key = max(
            [len(key) for key in commands_mapping.keys()] + [len("Command:")]
        )
        maxlen_value = max(
            [len(value[0]) for value in commands_mapping.values()] + [len("Signature:")]
        )
        maxlen_description = max(len(value[1]) for value in commands_mapping.values())

        text = "Available commands:\n"
        text += f"|-{''.ljust(maxlen_key, '-')}-|-{''.ljust(maxlen_value, '-')}-|-{''.ljust(maxlen_description, '-')}-|\n"
        text += f"| {'Command:'.ljust(maxlen_key)} | {'Signature:'.ljust(maxlen_value)} | {'Description:'.ljust(maxlen_description)} |\n"
        text += f"|-{''.ljust(maxlen_key, '-')}-|-{''.ljust(maxlen_value, '-')}-|-{''.ljust(maxlen_description, '-')}-|\n"
        text += "\n".join(
            f"| {key.ljust(maxlen_key)} | {value[0].ljust(maxlen_value)} | {value[1].ljust(maxlen_description)} |"
            for key, value in commands_mapping.items()
        )
        text += f"\n|-{''.ljust(maxlen_key, '-')}-|-{''.ljust(maxlen_value, '-')}-|-{''.ljust(maxlen_description, '-')}-|"

        if len(custom_commands_mapping) == 0:
            return text

        custom_commands_split = split_list(list(custom_commands_mapping.keys()), 3)
        maxlens = [max((len(key) for key in column), default=5) for column in custom_commands_split]

        text += "\n\nCustom commands:\n"
        text += f"|-{''.ljust(maxlens[0], '-')}-|-{''.ljust(maxlens[1], '-')}-|-{''.ljust(maxlens[2], '-')}-|\n"
        for i in range(len(custom_commands_split[0])):
            text += f"| {custom_commands_split[0][i].ljust(maxlens[0])} | {custom_commands_split[1][i].ljust(maxlens[1]) if  0 <= i < len(custom_commands_split[1]) else ''.ljust(maxlens[1])} | {custom_commands_split[2][i].ljust(maxlens[2]) if 0 <= i < len(custom_commands_split[2]) else ''.ljust(maxlens[2])} |\n"
        text += f"|-{''.ljust(maxlens[0], '-')}-|-{''.ljust(maxlens[1], '-')}-|-{''.ljust(maxlens[2], '-')}-|\n"
        return text

    async def generate_link(self, content: str) -> str:
        """Uploads the content to dpaste.com and returns the link.

        Args:
            content (str): The content to be uploaded.

        Returns:
            str: The link to the uploaded content.
        """
        async with self.context.bot.aiosession.post(
            "https://hastebin.cc/documents", data=content.encode("utf-8")
        ) as response:
            if response.status == 200:
                data = await response.json()
                return f"https://hastebin.cc/{data['key']}"
            else:
                raise Exception(f"Failed to post to Hastebin: {response.status}")

    async def send_help_message(self, user: discord.User) -> None:
        """This is the main function that handles the help command.
        It sends a message to the user with a list of available commands.
        If there are more than 7 commands, it sends a link to a dpaste.com with the full list in a table format.

        Args:
            user (discord.User): The user who invoked the help command.

        """
        commands_, custom_commands = await self.get_commands_mapping()
        command_names = list(commands_.keys())
        command_names += list(custom_commands.keys())
        if len(command_names) <= 7:
            return await user.send(f"Available commands: {', '.join(command_names)}")
        content = self.format_table(commands_, custom_commands)
        link = await self.generate_link(content)
        return await user.send(
            f"Available commands: {', '.join(list(command_names)[:7])} ...\nSnipped: <{link}>"
        )

    async def send_bot_help(self, mapping) -> None:
        """This function is called when the help command is invoked without any arguments.

        Args:
            mapping (Mapping[Optional[commands.Cog], List[commands.Command]]): A dictionary provided by discord.py containing the Cogs and their commands. Cog might be None for commands not in a cog.
        """
        user = self.context.author
        if isinstance(user, RelayMember):
            return await self.get_destination().send("I am not yet able to send DMs to minecraft.")
        await self.send_help_message(user)

    async def send_command_help(self, command) -> None:
        """This function is called when the help command is invoked with a command as an argument.

        Args:
            command (commands.Command): The command the user requested help for.
        """
        user = self.context.author
        if isinstance(user, RelayMember):
            return await self.get_destination().send("I am not yet able to send DMs to minecraft.")
        if len(command.signature) == 0:
            await user.send(
                f"Usage: `{self.context.bot.command_prefix[1]}{command.name}`"
            )
        else:
            await user.send(
                f"Usage: `{self.context.bot.command_prefix[1]}{command.name} {command.signature}`"
            )

class linkore:
    class CannotAccessLinkoreDB(Exception): ...

    @classmethod
    def get_discord_member_id(cls, name: str) -> int | None: ...

# TODO: Move to util:
def member_nick(name: str) -> str:
    # Luckly Minecraft Nicknames cannot contain [ or ] for now.
    # If they could, this function would have to be a bit more
    # complicated.
    return name.rsplit("[", 1)[-1].removesuffix("]")


class Patrick(commands.Bot):
    """The main class for the bot. It inherits from commands.Bot and is used to handle the bot's events and commands."""

    def __init__(self, logger_: logging.Logger, config_: dict):
        self.logger = logger_
        self.config = config_
        self.database = database.Connector()
        self.relay_regex: re.Pattern[str] = re.compile(
            self.config.get(
                "ingame_regex",
                r"^`([A-Za-z]+)` \*\*([A-Za-z0-9_\\]+)\*\*: *(.*)$",  # Load a default regex if not found in config as a fallback.
            )
        )
        activity = discord.Game("with Python")  # No more kotlin :)

        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        super().__init__(
            command_prefix=(
                ", ",
                ",",
            ),  # The prefix with an extra space was a suggestion in the discord server. Mobile users might have automatic spaces added after punctuation.
            case_insensitive=False,
            intents=intents,
            activity=activity,
            help_command=PatrickHelp(),  # Registering the custom help command.
        )

        # TODO: CREATE THIS FROM CONFIG
        self.member_roles: dict[str, int] = {}

        # ID of the current server (guild).
        self.server_id: int = self.config["server_id"] # type: ignore
        self.guild: discord.Guild = self.get_guild(self.server_id) # type: ignore
        self.logged_errors: set[str] = set()


    async def on_ready(self):
        """This function is called by discord.py when the bot is fully logged in and ready to use.
        It connects to the database and loads the extensions.
        """
        self.logger.info("Connecting to database")
        await self.database.connect()
        self.aiosession = ClientSession()
        await self.load_extensions()
        self.logger.info(f"Logged in as {self.user}")


    def is_network_message(self, message: discord.Message) -> bool:
        """
        Check wether a given message is a network message or not.
        """

        if not message.author.bot or message.channel.id != self.config["channels"]["gamechat"]:
            return False

        roles: list[discord.Role] = getattr(message.author, "roles", [])
        role_ids = [role.id for role in roles]
        return self.config["roles"]["network_bot"] in role_ids


    # TODO: Cached but cached result of a member is deleted if:
    #  - Member in cache leaves
    #  - Member uses ",link refresh"
    #  - Minecraft linked account uses ",link refresh"
    #@util.cached_linked_members
    async def get_linked_member(self, name: str, roles: collections.abc.Iterable[int]) -> discord.Member | discord.User | None:
        member = None
        try:
            id = linkore.get_discord_member_id(name)
            if not id is None:
                member = self.get_user(id)
        except linkore.CannotAccessLinkoreDB as err:
            if not str(err) in self.logged_errors:
                self.logged_errors.add(str(err))
                self.logger.error(str(err))

            for member in self.guild.members:
                if member_nick(member.display_name) == name:
                    break

            else:
                return None

        if member is None:
            return None

        return member


    async def on_message(self, message: discord.Message, /) -> None:
        """This function is an event listener that is called when a message is sent in a channel the bot can see.
        First it will check if the message is from the bot itself, if it is, it will ignore it.
        Then it will check if the message is from a bot, if it is, it will check if it matches the automod regexes.
        If it does, it will delete the message and return.
        After, this function will process the message to prepare it for command processing and hand it over to the command processor.

        Args:
            message (discord.Message): The message that was sent.
        """

        # Cancel any further actions if the message author was ourselves, to
        # prevent e.g. infinite recursion.
        if message.author == self.user:
            return

        if message.guild is not None and message.content.startswith("/link"):
            # If the message starts with /link, it's probably someone trying to link their account but not selecting the command from the popup.
            await message.channel.send(
                f"{escape_nickname(message.author.display_name)}: Please use the `/link` command from the command popup as you type. Do not type it out manually."
            )
            return await message.delete()

        if self.is_network_message(message):
            match = self.relay_regex.match(message.content)
            if not match:
                return logger.warning(
                    f"Network message from bot {user_log_repr(message.author)} didn't match relay regex."
                )

            role_name, user_name, content = match.groups()
            message = reformat_relay_chat(self, message, role_name, user_name,
                                          content)

            matches = find_automod_matches(self, content)
            if matches:
                logger.info(
                    f"Automod triggered for user {user_log_repr(message.author)} with message {message.content}"
                )
                channel = message.guild.get_channel(
                    self.config["channels"]["automod"]
                )
                embed = await create_automod_embed(
                    message.content,
                    matches,
                )
                await channel.send(
                    f"Flagged a message {message.jump_url}",
                    embed=embed,
                )

        await self.process_commands(message)


    def get_app_command(self, message: discord.Message) -> str:
        """
        Check wether the bot has a :class:`discord.app_commands.Command` who's
        name is a prefix for the message and return the message with the matched
        prefix removed, e.g.:

            >>> bot.command_prefix
            [',', ', ']
            >>> message.content
            ', addresponse'
            >>> bot.get_app_command(message)
            'addresponse'
            >>> message2.content
            ',hithere'
            >>> bot.get_app_command(message)
            ''

        Args:
            message (discord.Message): The message that might contain a valid
                                       app command.

        Returns:
            str: The matched app command name. If no name got matched, the string
                 is empty.
        """

        command_names = list(get_message_command_names(self, message.content))

        for command in self.commands:
            if (isinstance(command, discord.app_commands.Command)
                and command.name in command_names):
                return command.name

        return ""


    async def process_commands(self, message: discord.Message, /) -> None:
        """An override of the process_commands function to add custom command processing.
        This is called after on_message has prepared the message for command processing.

        Args:
            message (discord.Message): The message that was sent.
        """
        ctx = await self.get_context(
            message
        )  # get_context is a discord.py function that create a Context object from a message.
        if ctx.command is None and ctx.prefix is not None:
            # If the context found none, but there is a valid prefix, it means the user is trying to run a custom command.
            custom_command_ran = await process_custom_command(self, message)

            if not custom_command_ran:
                # A prefix was found, but no (custom) command was found. This means the user is trying to run a command that does not exist.
                self.logger.info(
                    f"User '{user_log_repr(ctx.author)}' attempted to run an unrecognized command: '{ctx.message.content[1:]}'"
                )

                app_cmd = self.get_app_command(message)
                if app_cmd:
                    # Slash-command for the message exists. Either the command
                    # was used in a raw form, e.g.
                    #     ,add
                    # or it had trailing arguments as well, like
                    #     ,add hello
                    # In either case, this errors and gives the app-command the
                    # user should have used.
                    error = f". Perhaps try the command as an app command (`/{app_cmd}`)?"
                else:
                    error = "Unrecognized command"

                await reply(ctx, error + " :'(")

            return

        if ctx.valid:
            # The context is valid when a command and prefix was found.
            # This is provided by discord.py and ensures that the context is valid for regular command processing
            self.logger.info(
                f"User '{user_log_repr(message.author)}' ran command '{ctx.command.name}'"
            )
            await self.database.add_command_history(
                message.author.display_name, ctx.command.name
            )
            await self.invoke(
                ctx
            )  # pass off to discord.py to handle the command processing.


    async def load_extensions(self):
        """A function to load all extension in the ./cogs directory.
        It will load all files that end with .py
        During loading, it will log the status of each extension.
        If an error occurs, it will continue to the next extension.
        The status and possible errors will be logged at the end of the loading process.
        """
        self.logger.info("Loading extensions")
        status: dict[str, typing.Literal["X", "L"]] = {}

        for extension in listdir("./cogs"):
            if extension.endswith(".py"):
                status[extension] = "X"  # Default to X for not loaded.

        if len(status) == 0:
            logger.info("No extensions found")
            return
        errors = []

        for extension in status:
            try:
                await self.load_extension(f"cogs.{extension[:-3]}")
                status[extension] = "L"  # Extension loaded and status should update
            except Exception as e:
                errors.append(
                    e
                )  # If an error occurs, it will be stored to be logged later.
        maxlen = max(
            len(str(extension)) for extension in status
        )  # Get the longest extension name to format the output.
        for extension in status:
            self.logger.info(f" {extension.ljust(maxlen)} | {status[extension]}")
        (
            self.logger.error(errors)
            if errors
            else self.logger.info("no errors during loading of extensions")
        )

    async def reload_extensions(self):
        """This function will unload all extensions currently loaded
        and then load everything from the ./cogs directory using the load_extensions function.
        """
        for extension in list(self.extensions):
            self.logger.info(f"Unloading extension {extension}")
            await self.unload_extension(extension)
        await self.load_extensions()


config = load_config()

# Set up logging
logging_settings = config.get("logging", {})
logging_level = logging_settings.get("level", "INFO").upper()
if logging_level in ("DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"):
    logger = setup_logger("patrick", logging_level, logging_settings)
else:
    print("Invalid logging level in config.yaml, defaulting to INFO")
    logger = setup_logger("patrick", "INFO", logging_settings)

patrick: Patrick = Patrick(logger, config)
load_automod_regexes(patrick)


@patrick.command(help="Sync slash commands")
@is_admin()
async def sync(ctx):
    patrick.logger.info("Syncing slash commands")
    commands_ = await patrick.tree.sync()
    patrick.logger.info(f"Synced {len(commands_)} slash commands")
    await reply(ctx, f"Synced {len(commands_)} slash commands")


@patrick.command(help="Reloads all extensions and configs. Admin only.")
@is_admin()
async def reload(ctx):
    await ctx.message.delete(delay=5)
    m: discord.Message = await reply(ctx, "Reloading extensions...")
    await patrick.reload_extensions()
    await m.edit(content="Reloaded extensions")
    await m.delete(delay=5)
    m: discord.Message = await reply(ctx, "Reloading config...")
    config_ = load_config()
    patrick.config = config_
    load_automod_regexes(patrick)
    await m.edit(content="Reloaded config")
    await m.delete(delay=5)


patrick.run(TOKEN, log_formatter=StreamLogFormatter(), log_level=logging_level)
