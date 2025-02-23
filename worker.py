import os
import subprocess
import json
import time
import logging
import signal
from concurrent.futures import ThreadPoolExecutor
import shutil
import argparse
import random
from pathlib import Path
from phrase import WORD_LIST
from dotenv import load_dotenv
import threading
import re

load_dotenv('cluster.env')

LOG_FILE = 'bot_manager.log'
SUPERVISORD_CONF_DIR = "/etc/supervisor/conf.d"
APP_DIR = Path("/app")
PIP_CACHE_DIR = APP_DIR / "pip_cache"
GLOBAL_VENV_TEMPLATE = APP_DIR / "venv_template"  # 🔥 Global virtualenv for speed

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.DEBUG, 
    format="%(asctime)s - %(levelname)s - %(message)s"
)

bot_lock = threading.Lock()

def generate_prefix():
    word1 = random.choice(WORD_LIST)
    word2 = random.choice(WORD_LIST)
    prefix = f"{word1} {word2}"
    logging.info(f'Generated prefix: {prefix}')
    return prefix

def load_config(file_path):
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
            clusters.append({
                "name": f"{prefix} {cluster['name']}",
                "bot_number": f"{prefix} {details[0]}",
                "git_url": details[1],
                "branch": details[2],
                "run_command": details[3],
                "env": details[4] if len(details) > 4 and isinstance(details[4], dict) else {}
            })
        except json.JSONDecodeError:
            logging.error(f"Error decoding JSON for {cluster['name']}, skipping.")
            continue
    return clusters

clusters = load_config("config.json")

def create_global_venv():
    """🔥 Create a global virtual environment to reuse for all bots."""
    if not GLOBAL_VENV_TEMPLATE.exists():
        logging.info(f'Creating global virtual environment at {GLOBAL_VENV_TEMPLATE}')
        subprocess.run(['python3', '-m', 'venv', str(GLOBAL_VENV_TEMPLATE)], check=True)

def install_global_dependencies(requirements_file):
    """🔥 Install dependencies globally once, then clone for each bot."""
    pip_exec = str(GLOBAL_VENV_TEMPLATE / "bin" / "pip")
    if requirements_file.exists():
        logging.info('Pre-installing dependencies in global venv for speed boost 🚀')
        subprocess.run([pip_exec, 'install', '--upgrade', 'pip', 'wheel'], check=True)
        subprocess.run([pip_exec, 'install', '--cache-dir', str(PIP_CACHE_DIR), '-r', str(requirements_file)], check=True)

def clone_venv(bot_venv):
    """🔥 Clone the global virtual environment instead of creating a new one from scratch."""
    if bot_venv.exists():
        shutil.rmtree(bot_venv)
    shutil.copytree(GLOBAL_VENV_TEMPLATE, bot_venv, symlinks=True)

def write_supervisord_config(cluster, command):
    """Write supervisord config."""
    bot_name = cluster['bot_number'].replace(" ", "_")
    venv_path = APP_DIR / bot_name / "venv"
    config_path = Path(SUPERVISORD_CONF_DIR) / f"{bot_name}.conf"
    
    logging.info(f"Writing supervisord config for {cluster['bot_number']} at {config_path}")

    env_vars = ','.join([f'{key}="{value}"' for key, value in cluster['env'].items()]) if cluster['env'] else ""

    config_content = f"""
[program:{bot_name}]
command={venv_path}/bin/python {command}
directory={APP_DIR}/{bot_name}
autostart=true
autorestart=true
stderr_logfile=/var/log/supervisor/{bot_name}_err.log
stdout_logfile=/var/log/supervisor/{bot_name}_out.log
environment={env_vars},VIRTUAL_ENV="{venv_path}",PATH="{venv_path}/bin:$PATH"
"""

    config_path.write_text(config_content.strip())
    logging.info(f"Supervisord config for {cluster['bot_number']} written successfully.")

def start_bot(cluster):
    """Clone, set up, and start a bot FAST 🔥."""
    with bot_lock:
        logging.info(f'Starting bot: {cluster["bot_number"]}')
        bot_name = cluster['bot_number'].replace(" ", "_")
        bot_dir = APP_DIR / bot_name
        venv_dir = bot_dir / "venv"
        requirements_file = bot_dir / 'requirements.txt'
        bot_file = bot_dir / cluster['run_command']
        branch = cluster.get('branch', 'main')

        try:
            if bot_dir.exists():
                logging.info(f'Removing existing directory: {bot_dir}')
                shutil.rmtree(bot_dir)

            logging.info(f'Cloning {cluster["bot_number"]} from {cluster["git_url"]} (branch: {branch})')
            subprocess.run(['git', 'clone', '-b', branch, '--single-branch', cluster['git_url'], str(bot_dir)], check=True)

            clone_venv(venv_dir)  # 🔥 Clone global virtualenv instead of creating new

            pip_exec = str(venv_dir / "bin" / "pip")
            python_exec = str(venv_dir / "bin" / "python")

            if requirements_file.exists():
                logging.info(f'Installing bot-specific dependencies for {cluster["bot_number"]}')
                subprocess.run([pip_exec, 'install', '--no-cache-dir', '-r', str(requirements_file)], check=True)

            command = str(bot_file)
            write_supervisord_config(cluster, command)
            reload_supervisord()
            logging.info(f"{cluster['bot_number']} started successfully via supervisord.")

        except subprocess.CalledProcessError as e:
            logging.error(f"Error while processing {cluster['bot_number']}: {e}")

def reload_supervisord():
    """Reload and update supervisord after modifying configurations."""
    logging.info("Reloading supervisord...")
    try:
        subprocess.run(["supervisorctl", "reread"], check=True)
        subprocess.run(["supervisorctl", "update"], check=True)
        logging.info("Supervisord updated successfully.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error reloading supervisord: {e}")

def main():
    logging.info('Initializing bot manager...')
    create_global_venv()
    global_requirements = Path("global_requirements.txt")  
    install_global_dependencies(global_requirements)  # 🔥 Install once, reuse always!

    with ThreadPoolExecutor(max_workers=len(clusters)) as executor:
        for cluster in clusters:
            executor.submit(start_bot, cluster)

if __name__ == "__main__":
    main()
