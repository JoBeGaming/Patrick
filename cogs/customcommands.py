import discord
from discord import app_commands
from discord.ext import commands

from util import app_is_staff, return_or_truncate, get_all_command_names


class ConfirmView(discord.ui.View):
    def __init__(self, callback, interaction: discord.Interaction) -> None:
        super().__init__(timeout=60)
        self.callback = callback
        self.original_interaction = interaction

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self.callback(interaction)
        for item in self.children:
            item.disabled = True
        await self.original_interaction.edit_original_response(view=self)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_message("Cancelled.", ephemeral=True)
        for item in self.children:
            item.disabled = True
        await self.original_interaction.edit_original_response(view=self)
        self.stop()

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        await self.original_interaction.edit_original_response(view=self)


class CustomCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        await self.bot.database.populate_cache()
        self.bot.logger.info("Custom commands loaded")

    @app_commands.command(description="Add a custom command to the bot.")
    @app_is_staff()
    async def add(self, interaction, key: str, *, message: str):
        commands_ = get_all_command_names(self.bot)
        if key in commands_:
            # The command is already a coded/built-in command. Don't allow adding it.
            await interaction.response.send_message(
                f"Command `{key}` is already a built-in command. Please choose a different name.",
                ephemeral=True,
            )
            return
        if key in self.bot.database.commands_cache:
            # The command already exists as a custom command. Don't allow adding it again.
            await interaction.response.send_message(
                f"Command `{key}` already exists. Use `addresponse` to add another response.",
                ephemeral=True,
            )
            return
        await self.bot.database.add_command(key, message)
        await interaction.response.send_message(
            f"Command `{key}` added.", ephemeral=True
        )

    @app_commands.command(
        name="addresponse",
        description="Add a response to an already existing command."
    )
    @app_is_staff()
    async def add_response(self, interaction, key: str, *, message: str):
        if key not in self.bot.database.commands_cache:
            await interaction.response.send_message(
                f"Command `{key}` does not exist.", ephemeral=True
            )
            return
        await self.bot.database.add_command_response(key, message)
        await interaction.response.send_message(
            f"Response added to command `{key}`.", ephemeral=True
        )

    @add_response.autocomplete("key")
    async def autocomplete_key(self, interaction, current: str):
        commands_ = self.bot.database.commands_cache
        return [
            app_commands.Choice(name=key, value=key)
            for key in commands_
            if current.lower() in key.lower()
        ]

    @app_commands.command(description="Remove a custom command from the bot.")
    @app_is_staff()
    async def remove(self, interaction, key: str):
        if key not in self.bot.database.commands_cache:
            await interaction.response.send_message(
                f"Command `{key}` does not exist.", ephemeral=True
            )
            return

        async def confirm_remove(interaction_: discord.Interaction):
            await self.bot.database.remove_command(key)
            await interaction_.response.send_message(
                f"Command `{key}` removed.", ephemeral=True
            )

        await interaction.response.send_message(
            f"Are you sure you want to remove command `{key}` and all responses linked to it?",
            view=ConfirmView(confirm_remove, interaction),
            ephemeral=True,
        )

    @remove.autocomplete("key")
    async def autocomplete_remove_key(self, interaction, current: str):
        commands_ = self.bot.database.commands_cache
        return [
            app_commands.Choice(name=key, value=key)
            for key in commands_
            if current.lower() in key.lower()
        ]

    @app_commands.command(
        name="removeresponse",
        description="Remove a response from an already existing command."
    )
    @app_is_staff()
    async def remove_response(self, interaction, key: str, *, message: str):
        if key not in self.bot.database.commands_cache:
            await interaction.response.send_message(
                f"Command `{key}` does not exist.", ephemeral=True
            )
            return
        if message not in self.bot.database.commands_cache[key]:
            await interaction.response.send_message(
                f"Response `{message}` does not exist for command `{key}`.",
                ephemeral=True,
            )
            return

        async def confirm_remove_response(interaction_: discord.Interaction):
            await self.bot.database.remove_command_response(key, message)
            await interaction_.response.send_message(
                f"Response `{return_or_truncate(message, 20)}` removed from command `{key}`.",
                ephemeral=True,
            )

        await interaction.response.send_message(
            f"Are you sure you want to remove response `{return_or_truncate(message, 20)}` from command `{key}`?",
            view=ConfirmView(confirm_remove_response, interaction),
            ephemeral=True,
        )

    @remove_response.autocomplete("key")
    async def autocomplete_remove_response_key(self, interaction, current: str):
        commands_ = self.bot.database.commands_cache
        return [
            app_commands.Choice(name=key, value=key)
            for key in commands_
            if current.lower() in key.lower()
        ]

    @remove_response.autocomplete("message")
    async def autocomplete_message(self, interaction, current: str):
        key = interaction.namespace.key
        if key not in self.bot.database.commands_cache:
            return []
        messages = self.bot.database.commands_cache[key]
        return [
            app_commands.Choice(name=message, value=message)
            for message in messages
            if current.lower() in message.lower()
        ]


async def setup(bot):
    await bot.add_cog(CustomCommands(bot))
