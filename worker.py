import os
from os import path as ospath
from sys import executable
from json import loads
from asyncio import create_subprocess_exec, run, sleep as asleep, gather, create_task
from asyncio.subprocess import DEVNULL

async def start_bot(bot_name, bot_config):
    for env_name, env_value in bot_config['env'].items():
        os.environ[env_name] = env_value

    bot_dir = f"/app/{bot_name}"
    bot_file = ospath.join(bot_dir, bot_config['run'])

    print(f'Starting {bot_name} bot with {bot_file}')
    return await create_subprocess_exec(executable, bot_file, cwd=bot_dir, env=os.environ, stdout=DEVNULL, stderr=DEVNULL)

async def main():
    with open("config.json", "r") as jsonfile:
        bots = loads(jsonfile)

    bot_tasks = []
    for bot_name, bot_config in bots.items():
        await asleep(2.5)
        bot_tasks.append(create_task(start_bot(bot_name, bot_config)))

    await gather(*(p.wait() for p in await gather(*bot_tasks)))


if __name__ == "__main__":
    run(main())