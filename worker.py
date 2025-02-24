import re
import os
import subprocess
import json
import time
import logging
import signal
import asyncio
import threading
import shutil
import argparse
import random
from pathlib import Path
from phrase import WORD_LIST
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

LOG_FILE = 'bot_manager.log'
SUPERVISORD_CONF_DIR = "/etc/supervisor/conf.d"
BOT_DIR = Path("/app")

# Configure log rotation
handler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=5)
logging.basicConfig(
    handlers=[handler],
    level=logging.DEBUG, 
    format="%(asctime)s - %(levelname)s - %(message)s"
)

bot_lock = threading.Lock()
clusters = []

def generate_prefix():
    """Generate a random prefix for bot naming."""
    word1, word2 = random.sample(WORD_LIST, 2)
    prefix = f"{word1} {word2}"
    logging.info(f'Generated prefix: {prefix}')
    return prefix

def validate_config(clusters):
    """Validate configuration to prevent errors."""
    required_keys = {'bot_number', 'git_url', 'branch', 'run_command'}
    bot_suffix_pattern = re.compile(r'bot\d+$')
    seen_bot_suffixes = set()

    for cluster in clusters:
        if not required_keys.issubset(cluster):
            logging.error(f"Missing required fields in {cluster.get('name', 'Unknown')}")
            return False

        if not cluster['git_url'].startswith('http'):
            logging.error(f"Invalid git_url for {cluster['name']}")
            return False

        match = bot_suffix_pattern.search(cluster['bot_number'])
        if not match:
            logging.error(f"Invalid bot_number format: {cluster['bot_number']}")
            return False

        bot_suffix = match.group()
        if bot_suffix in seen_bot_suffixes:
            logging.error(f"Duplicate bot suffix: {bot_suffix}")
            return False

        seen_bot_suffixes.add(bot_suffix)

    logging.info("Configuration validation successful.")
    return True

def load_config(file_path):
    """Load bot configurations from JSON file."""
    global clusters
    logging.info(f'Loading configuration from {file_path}')

    try:
        with open(file_path, "r") as jsonfile:
            config = json.load(jsonfile)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logging.error(f"Error loading JSON file: {e}")
        return

    new_clusters = []
    for cluster in config.get('clusters', []):
        details_str = os.getenv(cluster['name'], '{}')
        try:
            details = json.loads(details_str)
            if not isinstance(details, list) or len(details) < 4:
                logging.warning(f"Skipping cluster {cluster['name']} due to missing details.")
                continue

            prefix = generate_prefix()
            new_clusters.append({
                "name": f"{prefix} {cluster['name']}",
                "bot_number": f"{prefix} {details[0]}",
                "git_url": details[1],
                "branch": details[2],
                "run_command": details[3],
                "env": details[4] if len(details) > 4 and isinstance(details[4], dict) else {}
            })

        except json.JSONDecodeError:
            logging.error(f"Error decoding JSON for {cluster['name']}, skipping.")

    if validate_config(new_clusters):
        clusters = new_clusters
    else:
        raise ValueError("Invalid configuration file.")

class ConfigWatcher(FileSystemEventHandler):
    """Watch configuration file for changes."""
    def on_modified(self, event):
        if event.src_path.endswith("config.json"):
            logging.info("Config file changed, reloading...")
            load_config(event.src_path)
            restart_all_bots()

def start_config_watcher():
    """Start a watcher for dynamic config reloading."""
    event_handler = ConfigWatcher()
    observer = Observer()
    observer.schedule(event_handler, path=".", recursive=False)
    observer.start()

def write_supervisord_config(cluster, command):
    """Write supervisord config for each bot."""
    config_path = Path(SUPERVISORD_CONF_DIR) / f"{cluster['bot_number'].replace(' ', '_')}.conf"
    logging.info(f"Writing supervisord config for {cluster['bot_number']} at {config_path}")

    env_vars = ','.join([f'{key}="{value}"' for key, value in cluster['env'].items()]) if cluster['env'] else ""
    config_content = f"""
[program:{cluster['bot_number'].replace(' ', '_')}]
command={command}
directory={BOT_DIR}/{cluster['bot_number'].replace(' ', '_')}
autostart=true
autorestart=true
stderr_logfile=/var/log/supervisor/{cluster['bot_number'].replace(' ', '_')}_err.log
stdout_logfile=/var/log/supervisor/{cluster['bot_number'].replace(' ', '_')}_out.log
environment={env_vars}
"""
    config_path.write_text(config_content.strip())

async def start_bot(cluster):
    """Clone, set up, and start a bot with venv."""
    async with bot_lock:
        logging.info(f'Starting bot: {cluster["bot_number"]}')
        bot_dir = BOT_DIR / cluster['bot_number'].replace(" ", "_")
        venv_dir = bot_dir / "venv"
        branch = cluster.get('branch', 'main')

        try:
            if bot_dir.exists():
                shutil.rmtree(bot_dir)

            logging.info(f'Cloning bot from {cluster["git_url"]} (branch: {branch})')
            await asyncio.create_subprocess_exec('git', 'clone', '-b', branch, '--single-branch', cluster['git_url'], str(bot_dir))

            logging.info(f'Setting up virtual environment for {cluster["bot_number"]}')
            await asyncio.create_subprocess_exec('python3', '-m', 'venv', str(venv_dir))

            pip_path = venv_dir / "bin" / "pip"
            req_file = bot_dir / 'requirements.txt'
            if req_file.exists():
                logging.info(f'Installing dependencies for {cluster["bot_number"]}')
                await asyncio.create_subprocess_exec(str(pip_path), 'install', '--no-cache-dir', '-r', str(req_file))

            command = f"{venv_dir}/bin/python {bot_dir}/{cluster['run_command']}"
            write_supervisord_config(cluster, command)
            await reload_supervisord()

        except Exception as e:
            logging.error(f"Error while processing {cluster['bot_number']}: {e}")

async def reload_supervisord():
    """Reload supervisord asynchronously."""
    logging.info("Reloading supervisord...")
    await asyncio.create_subprocess_exec("supervisorctl", "reread")
    await asyncio.create_subprocess_exec("supervisorctl", "update")

def main():
    load_dotenv()
    load_config("config.json")
    start_config_watcher()

    logging.info('Starting bot manager...')
    asyncio.run(asyncio.gather(*[start_bot(cluster) for cluster in clusters]))

if __name__ == "__main__":
    main()
