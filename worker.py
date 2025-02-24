import os
import subprocess
import json
import time
import logging
import signal
import asyncio
import aiofiles
import psutil
import virtualenv
from concurrent.futures import ThreadPoolExecutor
import shutil
import argparse
import random
from pathlib import Path
from phrase import WORD_LIST
from logging.handlers import RotatingFileHandler
import threading
import re
from dotenv import load_dotenv
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from contextlib import asynccontextmanager

# Constants
LOG_FILE = 'bot_manager.log'
SUPERVISORD_CONF_DIR = "/etc/supervisor/conf.d"
CONFIG_FILE = "config.json"
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB
BACKUP_COUNT = 5
MAX_CONCURRENT_INSTALLS = 3
VENV_BASE_DIR = Path("/app/venvs")

# Configure logging with rotation
rotating_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=MAX_LOG_SIZE,
    backupCount=BACKUP_COUNT
)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[rotating_handler]
)

# Semaphore for resource management
install_semaphore = asyncio.Semaphore(MAX_CONCURRENT_INSTALLS)
bot_lock = threading.Lock()
config_lock = threading.Lock()
clusters = []

class ConfigWatcher(FileSystemEventHandler):
    def __init__(self, callback):
        self.callback = callback
        
    def on_modified(self, event):
        if event.src_path.endswith(CONFIG_FILE):
            logging.info("Config file modified, triggering reload...")
            asyncio.create_task(self.callback())

class ResourceManager:
    def __init__(self):
        self.max_memory_percent = 80
        self.max_cpu_percent = 80
    
    async def check_resources(self):
        cpu_percent = psutil.cpu_percent()
        memory_percent = psutil.virtual_memory().percent
        
        if cpu_percent > self.max_cpu_percent or memory_percent > self.max_memory_percent:
            await asyncio.sleep(5)  # Wait if resources are constrained
            return False
        return True

resource_manager = ResourceManager()

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
            logging.error(f"Duplicate bot suffix found: {bot_suffix}")
            return False
        seen_bot_suffixes.add(bot_suffix)

    return True

async def load_config(file_path):
    """Load bot configurations from a JSON file."""
    global clusters
    
    logging.info(f'Loading configuration from {file_path}')
    try:
        async with aiofiles.open(file_path, "r") as jsonfile:
            content = await jsonfile.read()
            config = json.loads(content)
    except Exception as e:
        logging.error(f"Error loading JSON file: {e}")
        return []

    new_clusters = []
    for cluster in config.get('clusters', []):
        details_str = os.getenv(cluster['name'], '{}')
        
        try:
            details = json.loads(details_str)
            if not isinstance(details, list) or len(details) < 4:
                continue

            prefix = generate_prefix()
            cluster_name = f"{prefix} {cluster['name']}"

            new_clusters.append({
                "name": cluster_name,
                "bot_number": f"{prefix} {details[0]}",
                "git_url": details[1],
                "branch": details[2],
                "run_command": details[3],
                "env": details[4] if len(details) > 4 and isinstance(details[4], dict) else {}
            })

        except json.JSONDecodeError:
            logging.error(f"Error decoding JSON for {cluster['name']}")
            continue

    if validate_config(new_clusters):
        with config_lock:
            clusters = new_clusters
        return new_clusters
    raise ValueError("Invalid configuration file")

async def create_venv(bot_dir):
    """Create a virtual environment for the bot."""
    venv_path = VENV_BASE_DIR / bot_dir.name
    if venv_path.exists():
        shutil.rmtree(venv_path)
    
    logging.info(f"Creating virtual environment at {venv_path}")
    virtualenv.create_environment(str(venv_path))
    return venv_path

async def write_supervisord_config(cluster, command, venv_path):
    """Write a supervisord config for the bot."""
    config_path = Path(SUPERVISORD_CONF_DIR) / f"{cluster['bot_number'].replace(' ', '_')}.conf"
    logging.info(f"Writing supervisord configuration for {cluster['bot_number']}")

    env_vars = ','.join([f'{key}="{value}"' for key, value in cluster['env'].items()]) if cluster['env'] else ""
    
    config_content = f"""
[program:{cluster['bot_number'].replace(' ', '_')}]
command={venv_path}/bin/python {command}
directory=/app/{cluster['bot_number'].replace(' ', '_')}
autostart=true
autorestart=true
stderr_logfile=/var/log/supervisor/{cluster['bot_number'].replace(' ', '_')}_err.log
stdout_logfile=/var/log/supervisor/{cluster['bot_number'].replace(' ', '_')}_out.log
stopasgroup=true
killasgroup=true
{f"environment={env_vars}" if env_vars else ""}
"""

    async with aiofiles.open(config_path, 'w') as f:
        await f.write(config_content.strip())

async def install_requirements(requirements_file, venv_path):
    """Install requirements in the virtual environment."""
    async with install_semaphore:
        while not await resource_manager.check_resources():
            await asyncio.sleep(1)
        
        pip_path = venv_path / 'bin' / 'pip'
        try:
            process = await asyncio.create_subprocess_exec(
                str(pip_path),
                'install',
                '--no-cache-dir',
                '-r',
                str(requirements_file),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            if process.returncode != 0:
                raise Exception(f"Failed to install requirements: {requirements_file}")
        except Exception as e:
            logging.error(f"Error installing requirements: {e}")
            raise

async def start_bot(cluster):
    """Clone, set up, and start a bot."""
    async with asynccontextmanager(lambda: bot_lock):
        logging.info(f'Starting bot: {cluster["bot_number"]}')
        bot_dir = Path('/app') / cluster['bot_number'].replace(" ", "_")
        requirements_file = bot_dir / 'requirements.txt'
        bot_file = bot_dir / cluster['run_command']
        branch = cluster.get('branch', 'main')

        try:
            if bot_dir.exists():
                shutil.rmtree(bot_dir)

            # Clone repository
            process = await asyncio.create_subprocess_exec(
                'git', 'clone', '-b', branch, '--single-branch',
                cluster['git_url'], str(bot_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()

            # Create and setup virtual environment
            venv_path = await create_venv(bot_dir)

            if requirements_file.exists():
                await install_requirements(requirements_file, venv_path)

            command = str(bot_file)
            await write_supervisord_config(cluster, command, venv_path)
            await reload_supervisord()

        except Exception as e:
            logging.error(f"Error while processing {cluster['bot_number']}: {e}")
            raise

async def reload_supervisord():
    """Reload and update supervisord after modifying configurations."""
    logging.info("Reloading supervisord...")
    try:
        process = await asyncio.create_subprocess_exec(
            "supervisorctl", "reread",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()
        
        process = await asyncio.create_subprocess_exec(
            "supervisorctl", "update",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()
        
        logging.info("Supervisord updated successfully")
    except Exception as e:
        logging.error(f"Error reloading supervisord: {e}")
        raise

async def stop_bot(bot_number):
    """Stop and remove a bot's supervisord configuration."""
    logging.info(f"Stopping bot: {bot_number}")
    bot_conf_name = bot_number.replace(" ", "_")
    
    try:
        process = await asyncio.create_subprocess_exec(
            "supervisorctl", "stop", bot_conf_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()
        
        conf_path = Path(SUPERVISORD_CONF_DIR) / f"{bot_conf_name}.conf"
        if conf_path.exists():
            conf_path.unlink()
        
        # Clean up virtual environment
        venv_path = VENV_BASE_DIR / bot_conf_name
        if venv_path.exists():
            shutil.rmtree(venv_path)
            
    except Exception as e:
        logging.error(f"Error stopping bot {bot_number}: {e}")

async def restart_all_bots():
    """Restart all bots managed by the system."""
    logging.info('Restarting all bots...')
    stop_tasks = [stop_bot(cluster['bot_number']) for cluster in clusters]
    await asyncio.gather(*stop_tasks)
    await reload_supervisord()

async def config_reload_handler():
    """Handle configuration file changes."""
    try:
        new_clusters = await load_config(CONFIG_FILE)
        await restart_all_bots()
        logging.info("Configuration reloaded successfully")
    except Exception as e:
        logging.error(f"Error reloading configuration: {e}")

def setup_config_watcher():
    """Set up file system watcher for config changes."""
    event_handler = ConfigWatcher(config_reload_handler)
    observer = Observer()
    observer.schedule(event_handler, path='.', recursive=False)
    observer.start()
    return observer

async def graceful_shutdown(sig, loop):
    """Handle graceful shutdown of the application."""
    logging.info(f'Received signal {sig.name}...')
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    
    for task in tasks:
        task.cancel()
    
    logging.info(f'Cancelling {len(tasks)} outstanding tasks')
    await asyncio.gather(*tasks, return_exceptions=True)
    await restart_all_bots()
    loop.stop()

async def main():
    """Main application entry point."""
    parser = argparse.ArgumentParser(description='Bot Manager')
    parser.add_argument('--restart', action='store_true', help='Restart all bots')
    args = parser.parse_args()

    # Initialize virtual environment directory
    VENV_BASE_DIR.mkdir(exist_ok=True)

    # Setup signal handlers
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(graceful_shutdown(s, loop))
        )

    # Load initial configuration
    await load_config(CONFIG_FILE)
    
    # Setup config file watcher
    observer = setup_config_watcher()

    try:
        if args.restart:
            await restart_all_bots()
        else:
            logging.info('Starting bot manager...')
            start_tasks = [start_bot(cluster) for cluster in clusters]
            await asyncio.gather(*start_tasks)
            
        # Keep the main loop running
        while True:
            await asyncio.sleep(1)
            
    except Exception as e:
        logging.error(f"Error in main loop: {e}")
    finally:
        observer.stop()
        observer.join()

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
