import os
import subprocess
import json
import time

with open("config.json", "r") as jsonfile:
    bots = json.load(jsonfile)

bot_processes = []
for bot_name, bot_config in bots.items():
    
    # sleep
    time.sleep(5)

    # Set the environment variables for this bot
    for env_name, env_value in bot_config['env'].items():
        os.environ[env_name] = env_value
    
    bot_dir = f"/app/{bot_name}"
    requirements_file = os.path.join(bot_dir, 'requirements.txt')
    bot_file = os.path.join(bot_dir, bot_config['run'])

    # Clone the bot repository
    # subprocess.run(['git', 'clone', bot_config['source'], bot_dir], check=True)
    
    # Install bot requirements
    # subprocess.run(['pip', 'install', '--no-cache-dir', '-r', requirements_file], check=True)
    
    # Run the bot
    print(f'Starting {bot_name} bot with {bot_file}')
    p = subprocess.Popen(['python3', bot_file], cwd=bot_dir, env=os.environ)
    bot_processes.append(p)

# Wait for all bot processes to complete
for p in bot_processes:
    p.wait()
