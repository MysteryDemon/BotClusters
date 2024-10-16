import os
import subprocess
import json
import time
import logging
import signal
from concurrent.futures import ThreadPoolExecutor
import shutil
import random
import socket
from pathlib import Path
from phrase import WORD_LIST
from logging.handlers import RotatingFileHandler

LOG_FILE = 'bot_manager.log'
handler = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3)  # 5 MB limit
logging.basicConfig(handlers=[handler], level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def generate_prefix():
    word1 = random.choice(WORD_LIST)
    word2 = random.choice(WORD_LIST)
    prefix = f"{word1} {word2}"
    logging.info(f'Generated prefix: {prefix}')
    return prefix 

def load_config(file_path):
    logging.info(f'Loading configuration from {file_path}')
    with open(file_path, "r") as jsonfile:
        bots = json.load(jsonfile)

    new_bots = {}
    for bot_name, bot_config in bots.items():
        prefix = generate_prefix() 
        prefixed_bot_name = f"{prefix} {bot_name}"

        if not all(key in bot_config for key in ['source', 'run', 'env']):
            logging.error(f"Configuration for {prefixed_bot_name} is missing required fields.")
            raise ValueError(f"Invalid configuration for {prefixed_bot_name}.")

        if not bot_config['source'].startswith('http'):
            logging.error(f"Invalid source URL for {prefixed_bot_name}.")
            raise ValueError(f"Invalid source URL for {prefixed_bot_name}.")

        new_bots[prefixed_bot_name] = bot_config
        logging.info(f'Loaded configuration for {prefixed_bot_name}')

    logging.info('Configuration loading complete.')
    return new_bots  

bots = load_config("config.json")
bot_processes = {}
tmux_sessions = {}

def create_tmux_session(session_name):
    logging.info(f'Creating tmux session: {session_name}')
    subprocess.run(['tmux', 'new-session', '-d', '-s', session_name])
    logging.info(f'Tmux session "{session_name}" created successfully.')

def attach_tmux_session(session_name):
    logging.info(f'Attaching to tmux session: {session_name}')
    subprocess.run(['tmux', 'attach-session', '-t', session_name])
    logging.info(f'Attached to tmux session "{session_name}".')

def kill_tmux_session(session_name):
    logging.info(f'Killing tmux session: {session_name}')
    subprocess.run(['tmux', 'kill-session', '-t', session_name])
    logging.info(f'Tmux session "{session_name}" killed.')

def manage_tmux_session(bot_name):
    session_name = f"{random.randint(100, 999)}_{bot_name.replace(' ', '_')}"
    create_tmux_session(session_name)
    tmux_sessions[bot_name] = session_name
    logging.info(f'Managed tmux session for bot "{bot_name}": {session_name}')
    return session_name

def start_bot(bot_name, bot_config):
    logging.info(f'Starting bot: {bot_name}')
    time.sleep(5)

    bot_env = os.environ.copy()

    for env_name, env_value in bot_config['env'].items():
        if env_value is not None:
            bot_env[env_name] = str(env_value)
            logging.info(f'Setting environment variable {env_name} for {bot_name}.')

    bot_dir = Path('/app') / bot_name.replace(" ", "_") 
    requirements_file = bot_dir / 'requirements.txt'
    bot_file = bot_dir / bot_config['run']
    branch = bot_config.get('branch', 'main')

    try:
        if not bot_dir.exists():
            logging.info(f'Creating directory for {bot_name}: {bot_dir}')
            bot_dir.mkdir(parents=True, exist_ok=True)

        if bot_dir.exists():
            logging.info(f'Removing existing directory: {bot_dir}')
            shutil.rmtree(bot_dir)

        logging.info(f'Cloning {bot_name} from {bot_config["source"]} (branch: {branch})')
        result = subprocess.run(['git', 'clone', '-b', branch, '--single-branch', bot_config['source'], str(bot_dir)], check=False, capture_output=True, text=True)

        if result.returncode != 0:
            logging.error(f"Error while cloning {bot_name}: {result.stderr}")
            return None

        logging.info(f'Installing requirements for {bot_name}')
        subprocess.run(['pip', 'install', '--no-cache-dir', '-r', str(requirements_file)], check=True)  # Ensure correct path

        session_name = manage_tmux_session(bot_name)

        env_export_cmds = ' '.join([f'export {key}="{value}"' for key, value in bot_env.items()])

        if bot_file.suffix == '.sh':
            logging.info(f'Starting {bot_name} bot with bash script: {bot_file}')
            subprocess.run(['tmux', 'send-keys', '-t', session_name, f'cd {bot_dir}', 'C-m'])
            subprocess.run(['tmux', 'send-keys', '-t', session_name, env_export_cmds, 'C-m'])
            subprocess.run(['tmux', 'send-keys', '-t', session_name, f'bash {bot_file}', 'C-m'])
        else:
            logging.info(f'Starting {bot_name} bot with Python script: {bot_file}')
            subprocess.run(['tmux', 'send-keys', '-t', session_name, f'cd {bot_dir}', 'C-m'])
            subprocess.run(['tmux', 'send-keys', '-t', session_name, env_export_cmds, 'C-m'])
            subprocess.run(['tmux', 'send-keys', '-t', session_name, f'python3 {bot_file}', 'C-m'])
    
        logging.info(f'{bot_name} started successfully.')
        return session_name
    except subprocess.CalledProcessError as e:
        logging.error(f"Error while processing {bot_name}: {e}")
        return None
    except OSError as e:
        logging.error(f"Unexpected error while starting {bot_name}: {e}")
        return None

def stop_bot(bot_name):
    logging.info(f'Stopping bot: {bot_name}')
    bot_process = bot_processes.get(bot_name)
    if bot_process:
        try:
            bot_process.terminate()
            bot_process.wait(timeout=5) 
            logging.info(f'Bot {bot_name} stopped successfully.')
        except subprocess.TimeoutExpired:
            logging.warning(f'Bot {bot_name} did not terminate in time; force killing...')
            bot_process.kill()
        finally:
            kill_tmux_session(tmux_sessions.get(bot_name)) 
    else:
        logging.warning(f'No running process found for bot: {bot_name}')

def cleanup_tmux_sessions():
    logging.info('Cleaning up tmux sessions...')
    result = subprocess.run(['tmux', 'ls'], capture_output=True, text=True)
    if result.returncode == 0:
        for session in result.stdout.splitlines():
            session_name = session.split(':')[0]
            if session_name not in tmux_sessions.values():
                kill_tmux_session(session_name)
    logging.info('Tmux session cleanup complete.')

def signal_handler(sig, frame):
    logging.info('Shutting down...')
    for bot_name in list(bot_processes.keys()):
        stop_bot(bot_name)
    logging.info('All bots and tmux sessions stopped.')
    exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def main():
    logging.info('Starting bot manager...')
    cleanup_tmux_sessions()  
    with ThreadPoolExecutor(max_workers=len(bots)) as executor:
        futures = {executor.submit(start_bot, name, config): name for name, config in bots.items()}

        for future in futures:
            try:
                future.result()
            except Exception as e:
                logging.error(f'Error in executing bot: {e}')

    logging.info('Bot manager has completed its tasks.')

if __name__ == "__main__":
    main()
    
