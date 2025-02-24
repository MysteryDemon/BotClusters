import os
import subprocess
import json
import time
import logging
import signal
import asyncio
import shutil
import argparse
import random
from pathlib import Path
from phrase import WORD_LIST
from logging.handlers import RotatingFileHandler
import re
from dotenv import load_dotenv
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

LOG_FILE = 'bot_manager.log'
SUPERVISORD_CONF_DIR = "/etc/supervisor/conf.d"
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
LOG_BACKUP_COUNT = 5

logging.basicConfig(
    handlers=[RotatingFileHandler(LOG_FILE, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT)],
    level=logging.DEBUG, 
    format="%(asctime)s - %(levelname)s - %(message)s"
)

bot_lock = asyncio.Lock()

def generate_prefix():
    """Generate a random prefix for bot naming."""
    word1 = random.choice(WORD_LIST)
    word2 = random.choice(WORD_LIST)
    prefix = f"{word1} {word2}"
    logging.info(f'Generated prefix: {prefix}')
    return prefix

def validate_config(clusters):
    """Ensure config is valid before starting bots."""
    required_keys = ['bot_number', 'git_url', 'branch', 'run_command']
    seen_bot_suffixes = set()
    bot_suffix_pattern = re.compile(r'bot\d+$')

    for cluster in clusters:
        if not all(key in cluster for key in required_keys):
            logging.error(f"Missing required fields in: {cluster.get('name', 'Unknown')}")
            return False

        if not cluster['git_url'].startswith('http'):
            logging.error(f"Invalid git_url for {cluster['name']}.")
            return False

        match = bot_suffix_pattern.search(cluster['bot_number'])
        if not match:
            logging.error(f"Invalid bot_number format for {cluster['name']}: {cluster['bot_number']}")
            return False
        
        bot_suffix = match.group()

        if bot_suffix in seen_bot_suffixes:
            logging.error(f"Duplicate bot suffix found: {bot_suffix} in {cluster['bot_number']}")
            return False
        
        seen_bot_suffixes.add(bot_suffix)

    logging.info("Configuration validation successful.")
    return True

def load_config(file_path):
    """Load bot configurations from a JSON file."""
    logging.info(f'Loading configuration from {file_path}')
    
    try:
        with open(file_path, "r") as jsonfile:
            config = json.load(jsonfile)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logging.error(f"Error loading JSON file: {e}")
        return []

    clusters = []
    for cluster in config.get('clusters', []):
        details_str = os.getenv(cluster['name'], '{}')
        
        try:
            details = json.loads(details_str)
            if not isinstance(details, list) or len(details) < 4:
                logging.warning(f"Skipping cluster {cluster['name']} due to missing details.")
                continue

            prefix = generate_prefix()
            cluster_name = f"{prefix} {cluster['name']}"

            clusters.append({
                "name": cluster_name,
                "bot_number": f"{prefix} {details[0]}",
                "git_url": details[1],
                "branch": details[2],
                "run_command": details[3],
                "env": details[4] if len(details) > 4 and isinstance(details[4], dict) else {}
            })

        except json.JSONDecodeError:
            logging.error(f"Error decoding JSON for {cluster['name']}, skipping.")
            continue

    if not validate_config(clusters):
        raise ValueError("Invalid configuration file.")

    return clusters

load_dotenv()
clusters = load_config("config.json")

def write_supervisord_config(cluster, command):
    """Write a supervisord config for the bot."""
    config_path = Path(SUPERVISORD_CONF_DIR) / f"{cluster['bot_number'].replace(' ', '_')}.conf"
    logging.info(f"Writing supervisord configuration for {cluster['bot_number']} at {config_path}")

    env_vars = ','.join([f'{key}="{value}"' for key, value in cluster['env'].items()]) if cluster['env'] else ""

    config_content = f"""
[program:{cluster['bot_number'].replace(' ', '_')}]
command={command}
directory=/app/{cluster['bot_number'].replace(' ', '_')}
autostart=true
autorestart=true
stderr_logfile=/var/log/supervisor/{cluster['bot_number'].replace(' ', '_')}_err.log
stdout_logfile=/var/log/supervisor/{cluster['bot_number'].replace(' ', '_')}_out.log
{f"environment={env_vars}" if env_vars else ""}
"""

    config_path.write_text(config_content.strip())
    logging.info(f"Supervisord configuration for {cluster['bot_number']} written successfully.")

async def start_bot(cluster):
    """Clone, set up, and start a bot."""
    async with bot_lock:
        logging.info(f'Starting bot: {cluster["bot_number"]}')
        bot_env = os.environ.copy()
        bot_env.update(cluster.get('env', {}))
        bot_dir = Path('/app') / cluster['bot_number'].replace(" ", "_")
        requirements_file = bot_dir / 'requirements.txt'
        bot_file = bot_dir / cluster['run_command']
        branch = cluster.get('branch', 'main')

        try:
            if bot_dir.exists():
                logging.info(f'Removing existing directory: {bot_dir}')
                shutil.rmtree(bot_dir)

            logging.info(f'Cloning {cluster["bot_number"]} from {cluster["git_url"]} (branch: {branch})')
            await asyncio.create_subprocess_exec('git', 'clone', '-b', branch, '--single-branch', cluster['git_url'], str(bot_dir))

            venv_dir = bot_dir / 'venv'
            logging.info(f'Creating virtual environment for {cluster["bot_number"]}')
            await asyncio.create_subprocess_exec('python3', '-m', 'venv', str(venv_dir))

            if requirements_file.exists():
                logging.info(f'Installing requirements for {cluster["bot_number"]} in virtual environment')
                await asyncio.create_subprocess_exec(str(venv_dir / 'bin' / 'pip'), 'install', '--no-cache-dir', '-r', str(requirements_file))

            command = f"bash {bot_file}" if bot_file.suffix == ".sh" else f"{venv_dir / 'bin' / 'python3'} {bot_file}"
            write_supervisord_config(cluster, command)
            await reload_supervisord()
            logging.info(f"{cluster['bot_number']} started successfully via supervisord.")

        except subprocess.CalledProcessError as e:
            logging.error(f"Error while processing {cluster['bot_number']}: {e}")

async def reload_supervisord():
    """Reload and update supervisord after modifying configurations."""
    logging.info("Reloading supervisord...")
    try:
        await asyncio.create_subprocess_exec("supervisorctl", "reread")
        await asyncio.create_subprocess_exec("supervisorctl", "update")
        logging.info("Supervisord updated successfully.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error reloading supervisord: {e}")

async def stop_bot(bot_number):
    """Stop and remove a bot's supervisord configuration."""
    logging.info(f"Stopping bot: {bot_number}")
    bot_conf_name = bot_number.replace(" ", "_")
    
    try:
        await asyncio.create_subprocess_exec("supervisorctl", "stop", bot_conf_name)
    except subprocess.CalledProcessError:
        logging.error(f"Failed to stop bot {bot_number}")

    conf_path = Path(SUPERVISORD_CONF_DIR) / f"{bot_conf_name}.conf"
    if conf_path.exists():
        conf_path.unlink()
        logging.info(f"Removed supervisord configuration for {bot_number}.")
    await reload_supervisord()

async def restart_all_bots():
    """Restart all bots managed by the system."""
    logging.info('Restarting all bots...')
    for cluster in clusters:
        await stop_bot(cluster['bot_number'])
    await reload_supervisord()

def signal_handler(sig, frame):
    logging.info('Shutting down...')
    loop = asyncio.get_event_loop()
    loop.run_until_complete(restart_all_bots())
    exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

class ConfigReloadHandler(FileSystemEventHandler):
    """Handler to reload configuration when the config file changes."""
    def on_modified(self, event):
        if event.src_path.endswith("config.json"):
            logging.info("Configuration file changed, reloading...")
            global clusters
            clusters = load_config("config.json")
            logging.info("Configuration reloaded successfully.")

def start_config_watcher():
    """Start the config file watcher."""
    event_handler = ConfigReloadHandler()
    observer = Observer()
    observer.schedule(event_handler, path='.', recursive=False)
    observer.start()
    return observer

async def main():
    parser = argparse.ArgumentParser(description='Bot Manager')
    parser.add_argument('--restart', action='store_true', help='Restart all bots')
    args = parser.parse_args()

    start_config_watcher()

    if args.restart:
        await restart_all_bots()
    else:
        logging.info('Starting bot manager...')
        tasks = [start_bot(cluster) for cluster in clusters]
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
