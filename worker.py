import os
import subprocess
import json
import time
import logging
import signal
from concurrent.futures import ThreadPoolExecutor
import shutil
from logging.handlers import RotatingFileHandler
import socket

LOG_FILE = 'bot_manager.log'
handler = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3)  # 5 MB limit
logging.basicConfig(handlers=[handler], level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_config(file_path):
    with open(file_path, "r") as jsonfile:
        bots = json.load(jsonfile)

    for bot_name, bot_config in bots.items():
        if 'source' not in bot_config or 'run' not in bot_config or 'env' not in bot_config:
            logging.error(f"Configuration for {bot_name} is missing required fields.")
            raise ValueError(f"Invalid configuration for {bot_name}.")
    return bots

bots = load_config("config.json")
bot_processes = {}
bot_failure_count = {}

def find_available_port(start_port=5000, max_retries=10):
    port = start_port
    retries = 0

    while retries < max_retries:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('0.0.0.0', port))
                return port
            except OSError as err:
                if err.errno == 98:  # Port is already in use
                    port += 1
                    retries += 1
                else:
                    raise

    raise OSError(f"Could not find an available port after {max_retries} retries.")

def start_bot(bot_name, bot_config):
    time.sleep(5)

    # Create a copy of the environment variables for this bot
    bot_env = os.environ.copy()

    # Loop through and set all environment variables for this bot
    for env_name, env_value in bot_config['env'].items():
        if env_value is not None:  # Ensure value is not None
            bot_env[env_name] = str(env_value)  # Convert all values to strings

    if 'PORT' in bot_config['env']:
        port = find_available_port(int(bot_config['env']['PORT']))
        bot_env['PORT'] = str(port)  # Update the copied environment with the new port
        logging.info(f'{bot_name} assigned to port {port}')
    else:
        logging.warning(f'{bot_name} has no PORT defined in env.')

    bot_dir = f"/app/{bot_name}"
    requirements_file = os.path.join(bot_dir, 'requirements.txt')
    bot_file = os.path.join(bot_dir, bot_config['run'])
    branch = bot_config.get('branch', 'main')

    try:
        if os.path.exists(bot_dir):
            logging.info(f'Removing existing directory: {bot_dir}')
            shutil.rmtree(bot_dir)

        logging.info(f'Cloning {bot_name} from {bot_config["source"]} (branch: {branch})')
        result = subprocess.run(['git', 'clone', '-b', branch, '--single-branch', bot_config['source'], bot_dir], check=False, capture_output=True, text=True)

        if result.returncode != 0:
            logging.error(f"Error while cloning {bot_name}: {result.stderr}")
            return None

        logging.info(f'Installing requirements for {bot_name}')
        subprocess.run(['pip', 'install', '--no-cache-dir', '-r', requirements_file], check=True)

        if bot_file.endswith('.sh'):
            logging.info(f'Starting {bot_name} bot with bash script: {bot_file}')
            p = subprocess.Popen(['bash', bot_file], cwd=bot_dir, env=bot_env)  # Use bot_env here
        else:
            logging.info(f'Starting {bot_name} bot with Python script: {bot_file}')
            p = subprocess.Popen(['python3', bot_file], cwd=bot_dir, env=bot_env)  # Use bot_env here

        return p
    except subprocess.CalledProcessError as e:
        logging.error(f"Error while processing {bot_name}: {e}")
        return None
    except OSError as e:
        if e.errno == 98:
            logging.error(f"Port conflict for {bot_name}. Retrying with a new port...")
            return start_bot(bot_name, bot_config)
        else:
            logging.error(f"Unexpected error while starting {bot_name}: {e}")
            return None

def stop_bot(bot_name):
    logging.info(f'Stopping {bot_name}...')
    bot_process = bot_processes.get(bot_name)
    if bot_process:
        bot_process.terminate()
        bot_process.wait()

def manage_bot(bot_name, bot_config):
    failure_count = 0
    max_failures = 2

    while True:
        bot_process = start_bot(bot_name, bot_config)
        if bot_process is not None:
            bot_processes[bot_name] = bot_process
            failure_count = 0
        else:
            failure_count += 1
            logging.warning(f'{bot_name} failed to start ({failure_count}/{max_failures}).')

        if failure_count >= max_failures:
            logging.error(f'{bot_name} has failed to start {max_failures} times in a row. Stopping restarts.')
            break

        if bot_process:
            bot_process.wait()
            logging.info(f'{bot_name} has stopped. Restarting...')

def signal_handler(sig, frame):
    logging.info('Shutting down...')
    for bot_name in bot_processes.keys():
        stop_bot(bot_name)
    exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def main():
    with ThreadPoolExecutor(max_workers=len(bots)) as executor:
        futures = {executor.submit(manage_bot, name, config): name for name, config in bots.items()}

        for future in futures:
            future.result()

if __name__ == "__main__":
    main()
    
