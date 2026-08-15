import asyncio
import csv

import database


async def main():
    database_ = database.Connector()
    await database_.connect()
    with open("to_import.csv", "r", encoding="utf8") as source:
        reader = csv.DictReader(source)
        for cmd in reader:
            print(f"Adding {cmd}")
            await database_.add_command(cmd["key"], cmd["response"])
    await database_.close()
    print("Done")


if __name__ == '__main__':
    asyncio.run(main())
