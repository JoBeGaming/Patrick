import aiosqlite
import collections.abc
from datetime import datetime, timezone
import pathlib


def convert_datetime(val: bytes) -> datetime:
    """
    Convert ISO 8601 datetime to datetime.datetime object.
    """

    return datetime.fromisoformat(val.decode())


aiosqlite.register_converter("datetime", convert_datetime)


class Connector:
    def __init__(self) -> None:
        self.database = pathlib.Path(__file__).parent / "commands.db"
        self._connection: aiosqlite.Connection | None = None

        # A cache dictionary for custom commands. The keys are the command names, and the value is a list of responses.
        self.commands_cache: collections.abc.MutableMapping[str, list[str]] = collections.defaultdict(list)

    @property
    def connection(self) -> aiosqlite.Connection:
        if self._connection is None:
            self._connection = aiosqlite.connect(self.database, detect_types=True)

        return self._connection

    async def connect(self) -> None:
        """
        Connect to the SQLite database and create the necessary tables if they
        do not exist yet.
        """

        async with self.connection.cursor() as cursor:
            await cursor.execute(
                """CREATE TABLE IF NOT EXISTS command_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key VARCHAR(128)
                )"""
            )
            await cursor.execute(
                """CREATE TABLE IF NOT EXISTS command_responses (
                    id INTEGER,
                    response TEXT
                )"""
            )
            await cursor.execute(
                """CREATE TABLE IF NOT EXISTS command_history (
                    user INTEGER,
                    command VARCHAR(128),
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )"""
            )
            await cursor.execute(
                """CREATE TABLE IF NOT EXISTS timers (
                    user_id INTEGER,
                    name VARCHAR(128),
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )"""
            )
            await cursor.execute(
                """CREATE TABLE IF NOT EXISTS reminders (
                    user_id INTEGER,
                    channel_id INTEGER,
                    message TEXT,
                    timestamp DATETIME
                )"""
            )
            await cursor.execute(
                """CREATE TABLE IF NOT EXISTS tempbans (
                    user_id INTEGER,
                    reason TEXT,
                    timestamp DATETIME
                )"""
            )

            await self.connection.commit()

    async def close(self) -> None:
        await self.connection.close()

    # TODO: Rework caching system
    async def populate_cache(self) -> None:
        """
        Populate the commands_cache dictionary with the keys and responses from
        the database. The keys are the command names, and the value is a list of
        responses.
        """

        async with self.connection.cursor() as cursor:
            await cursor.execute(
                "SELECT key, response FROM command_keys JOIN command_responses ON command_keys.id = command_responses.id"
            )

            rows = await cursor.fetchall()
            for key, response in rows:
                self.commands_cache[key].append(response)

    async def get_command(self, key: str):
        """
        Get a command from the cache. If the command is not in the cache, return None.

        Args:
            key (str): The command to get

        Returns:
            list: A list of responses for the command, or None if the command is not in the cache.
        """
        return self.commands_cache.get(key)

    async def add_command(self, key: str, response: str) -> None:
        """
        Add a command to the database and cache. The command is a key in the commands_cache dictionary, and the value is an initial response.
        The command is added to the command_keys table, and the response is added to the command_responses table with a foreign key reference to the command_keys table.

        Args:
            key (str): The command name
            response (str): The initial response for the command
        """

        async with self.connection.cursor() as cur:
            query = "INSERT INTO command_keys(key) VALUES(?)"
            await cur.execute(query, (key,))
            command_id = cur.lastrowid
            query = "INSERT INTO command_responses(id, response) VALUES(?, ?)"
            await cur.execute(query, (command_id, response))
            await self.connection.commit()
            self.commands_cache[key] = [response]

    async def remove_command(self, key: str) -> None:
        """Remove a command from the database and cache. The command is removed from the command_keys table, and all responses linked to it are removed from the command_responses table.

        Args:
            key (str): The command name to remove
        """
        async with self.connection.cursor() as cur:
            query = "DELETE FROM command_responses WHERE id = (SELECT id FROM command_keys WHERE key = ?)"
            await cur.execute(query, (key,))
            query = "DELETE FROM command_keys WHERE key = ?"
            await cur.execute(query, (key,))
            await self.connection.commit()
            if key in self.commands_cache:
                del self.commands_cache[key]

    async def add_command_response(self, key: str, response: str) -> None:
        """Add a response to an already existing command. The response is added to the command_responses table with a foreign key reference to the command_keys table.
        The response is also added to the commands_cache dictionary for the command.
        TODO: This function does not check if the command exists in the database and should only be used if the command is already in the cache.

        Args:
            key (str): The name of the command to add a response to
            response (str): The response to add to the command
        """

        async with self.connection.cursor() as cur:
            query = "INSERT INTO command_responses(id, response) VALUES((SELECT id FROM command_keys WHERE key = ?), ?)"
            await cur.execute(query, (key, response))
            await self.connection.commit()
            if key in self.commands_cache:
                self.commands_cache[key].append(response)

    async def remove_command_response(self, key: str, response: str) -> None:
        """Removes a response from an already existing command. The response is removed from the command_responses table.
        TODO: This function does not check if the command exists in the database and should only be used if the command is already in the cache.
        The command is removed from the command_keys table if it has no responses left.

        Args:
            key (str): The name of the command to remove a response from
            response (str): The response to remove
        """
        async with self.connection.cursor() as cur:
            query = "DELETE FROM command_responses WHERE id = (SELECT id FROM command_keys WHERE key = ?) AND response = ?"
            await cur.execute(query, (key, response))
            if key in self.commands_cache and response in self.commands_cache[key]:
                self.commands_cache[key].remove(response)
            # If the command has no responses left, remove it from the cache and database
            if not self.commands_cache[key]:
                del self.commands_cache[key]
                query = "DELETE FROM command_keys WHERE key = ?"
                await cur.execute(query, (key,))
            await self.connection.commit()

    async def add_command_history(self, user: str, command: str) -> None:
        """Add a histry entry to the database when a command is ran.

        Args:
            user (str): The name of the user who ran the command
            command (str): The name of the command that was ran
        """

        async with self.connection.cursor() as cur:
            query = "INSERT INTO command_history(user, command) VALUES(?, ?)"
            await cur.execute(query, (user, command))
            await self.connection.commit()

    async def start_timer(self, user_id: int, name: str) -> None:
        """Start a timer for a user. The timer is stored in the database with the user's ID and the name of the timer.

        Args:
            user_id (int): The ID of the user who started the timer
            name (str): The name of the timer
        """

        async with self.connection.cursor() as cur:
            query = "INSERT INTO timers(user_id, name, timestamp) VALUES(?, ?, ?)"
            await cur.execute(query, (user_id, name, datetime.now(timezone.utc)))
            await self.connection.commit()

    async def stop_timer(self, user_id: int, name: str):
        """Stop a timer for a user. The timer is removed from the database.

        Args:
            user_id (int): The ID of the user who stopped the timer
            name (str): The name of the timer
        """

        # TODO: WHAT IF THE query RETURNS [] CHECKF ROR UID
        async with self.connection.cursor() as cur:
            query = (
                "DELETE FROM timers WHERE user_id = ? AND name = ? RETURNING timestamp"
            )
            await cur.execute(query, (user_id, name))
            rows = await cur.fetchall()
            await self.connection.commit()
            return rows

    # TODO: DOESNT RETURN STR, STR DOES IT
    async def get_timers(self, user_id: int) -> collections.abc.Iterable[aiosqlite.Row[str, str]]:
        """Get all timers for a user. The timers are returned as a list of tuples with the name and timestamp of each timer.

        Args:
            user_id (int): The ID of the user to get timers for

        Returns:
            list: A list of tuples with the name and timestamp of each timer
        """
        async with self.connection.cursor() as cur:
            query = "SELECT name, timestamp FROM timers WHERE user_id = ?"
            await cur.execute(query, (user_id,))
            rows = await cur.fetchall()
            await self.connection.commit()
            return rows

    async def add_reminder(self, user_id: int, channel_id: int, message: str, timestamp: datetime) -> None:
        """Add a reminder for a user. The reminder is stored in the database with the user's ID, message, and timestamp.

        Args:
            user_id (int): The ID of the user who set the reminder
            channel_id (int): The ID of the channel where the reminder should be sent
            message (str): The message for the reminder
            timestamp (datetime): The time when the reminder should be triggered
        """

        async with self.connection.cursor() as cur:
            query = "INSERT INTO reminders(user_id, channel_id, message, timestamp) VALUES(?, ?, ?, ?)"
            await cur.execute(query, (user_id, channel_id, message, timestamp))
            await self.connection.commit()

    # TODO: str, int, timestamp idk
    async def get_reminders(self, user_id: int) -> collections.abc.Iterable[aiosqlite.Row[str, int, str]]:
        """Get all reminders for a user. The reminders are returned as a list of tuples with the message and timestamp of each reminder.

        Args:
            user_id (int): The ID of the user to get reminders for

        Returns:
            list: A list of tuples with the message, channel and timestamp of each reminder
        """
        async with self.connection.cursor() as cur:
            query = "SELECT message, channel_id, timestamp FROM reminders WHERE user_id = ?"
            await cur.execute(query, (user_id,))
            rows = await cur.fetchall()
            return rows

    # TODO: int, int, str
    async def pop_expired_reminders(self) -> collections.abc.Iterable[aiosqlite.Row[int, int, str]]:
        """Remove all expired reminders from the database. A reminder is considered expired if its timestamp is in the past."""
        async with self.connection.cursor() as cur:
            query = "DELETE FROM reminders WHERE timestamp < ? RETURNING user_id, channel_id, message"
            await cur.execute(query, (datetime.now(timezone.utc),))
            rows = await cur.fetchall()
            await self.connection.commit()
            return rows

    async def add_tempban(self, user_id: int, reason: str, timestamp: datetime) -> None:
        """Add a temporary ban for a user. The ban is stored in the database with the user's ID, reason, and expiration time.

        Args:
            user_id (int): The ID of the user to ban
            reason (str): The reason for the ban
            timestamp (datetime): The time when the ban expires
        """
        async with self.connection.cursor() as cur:
            query = "INSERT INTO tempbans(user_id, reason, timestamp) VALUES(?, ?, ?)"
            await cur.execute(query, (user_id, reason, timestamp))
            await self.connection.commit()

    # TODO: int
    async def pop_expired_tempbans(self) -> collections.abc.Iterable[aiosqlite.Row[int]]:
        """Remove all expired temporary bans from the database. A ban is considered expired if its timestamp is in the past."""
        async with self.connection.cursor() as cur:
            query = "DELETE FROM tempbans WHERE timestamp < ? RETURNING user_id"
            await cur.execute(query, (datetime.now(timezone.utc),))
            rows = await cur.fetchall()
            await self.connection.commit()
            return rows


async def a():
    c = Connector()
    r = await c.pop_expired_reminders()
    for l in r:
        x = iter(l)
        for i in iter(l):
            print(i)