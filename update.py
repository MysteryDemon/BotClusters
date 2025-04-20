from os import path as opath, getenv
from logging import FileHandler, StreamHandler, INFO, basicConfig, error as log_error, info as log_info
from logging.handlers import RotatingFileHandler
from subprocess import run as srun, CalledProcessError
from dotenv import load_dotenv

if opath.exists("log.txt"):
    with open("log.txt", 'r+') as f:
        f.truncate(0)

basicConfig(format="[%(asctime)s] [%(name)s | %(levelname)s] - %(message)s [%(filename)s:%(lineno)d]",
            datefmt="%m/%d/%Y, %H:%M:%S %p",
            handlers=[FileHandler('log.txt'), StreamHandler()],
            level=INFO)

load_dotenv('cluster.env', override=True)

UPSTREAM_REPO = getenv("UPSTREAM_REPO", "https://github.com/MysteryDemon/BotClusters")
UPSTREAM_BRANCH = getenv("UPSTREAM_BRANCH", "master")

if UPSTREAM_REPO is not None:
    if opath.exists('.git'):
        srun(["rm", "-rf", ".git"])

    try:
        # Initialize git repository
        srun(["git", "init", "-q"], check=True)
        
        # Set global git user configuration
        srun(["git", "config", "--global", "user.email", "mysteryxdemon@gmail.com"], check=True)
        srun(["git", "config", "--global", "user.name", "mysterydemon"], check=True)
        
        # Add files to the repository and commit
        srun(["git", "add", "."], check=True)
        srun(["git", "commit", "-sm", "update", "-q"], check=True)
        
        # Add remote origin and fetch updates
        srun(["git", "remote", "add", "origin", UPSTREAM_REPO], check=True)
        srun(["git", "fetch", "origin", "-q"], check=True)
        
        # Reset the local branch to match upstream
        srun(["git", "reset", "--hard", f"origin/{UPSTREAM_BRANCH}", "-q"], check=True)

        log_info('Successfully updated with the latest commit from UPSTREAM_REPO')
    except CalledProcessError as e:
        log_error(f'Something went wrong while updating, check UPSTREAM_REPO if valid or not! Error: {str(e)}')
