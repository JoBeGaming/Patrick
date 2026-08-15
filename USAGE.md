# Basic introduction to using patrick

Patrick is a multi-purpose discord bot designed for the ORE community.
Please first consult the README.md for detailed information on how to set up Patrick.

## Commands

Commands are the primary way to interact with Patrick. They allow you to perform various actions. Most commands use the old text based system with prefix `,`. Some commands may also use discord's built in slash-command system. These commands are denoted by an asterisk `*` before their name. Some commands may be discord's "context command" system, for which you need to right click a user or message to see this command and use it. These are denoted by an ampersand `&` before their name.

### No category

- sync: Admin only command. Forces an app commands sync with discord. Required for proper functioning of slash and context commands.
- reload: Admin only command. Reloads the bot's configuration and commands. Commands in this category are excluded due to technical reasons.
- help: Shows a list of all available commands. Also sends the user a DM with a link to a more detailed explanation of commands.

### cOREmands

- apply: Shows info how users can apply for roles in the ORE community.
- trust: Moderator command to grant a user the "trusted" role.
- &delete_message: Deletes the selected message. This pops up a modal in the discord client to enter a reason for removal.

### Custom commands

- *add: Mod only. Adds a new custom command with a response to the bot. Only a single response can be given here
- *add_response: Mod only. Adds a new response to an already existing command. When multiple responses exist, the bot will choose a random one.
- *remove: Mod only. Removes a command and all responses to it. This action cannot be undone.
- *remove_response: Mod only. Removes a response from an existing command. If all responses are removed, the command itself is also removed. This action cannot be undone.

### Random commands

- ping: Measures the bot's latency and processing time.
- quote: Get a random zenquotes quote.
- xkcd: Get a random or specified xkcd and display it.
- rng: Generate a random binary number with the given amount of digits.
- roll: Roll the dice! Accepts full DnD dice notation.
- uuid: Gets uuid of a minecraft username.
- slap: Rude >:(. Grants the "slapped" rank.
- pikl: Mod only. Grants the "pikl" rank for a short time.
- google: Generates a google search link for the given query.
- factorize: Calculates prime factorization of a given number.
- aeiou: Aeiou.
- fractal: Mod only. Generates a fractal image from the given prompt to use as a random seed.
- insult: Why you booing me?

### Reminders

- remindme: set a reminder for a specific time and date and given text
- reminders: see your reminders

### Timers

- timer: Base command. Doesn't do anything.
- timer start: start a timer with a given text.
- timer stop: stops a timer and displays the elapsed time.
- timer list: list all your active timers
