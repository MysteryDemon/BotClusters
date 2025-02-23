import os
import logging
from app import create_app, socketio

app = create_app()

SUPERVISOR_LOG_DIR = "/var/log/supervisor"
os.makedirs(SUPERVISOR_LOG_DIR, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(SUPERVISOR_LOG_DIR, "app.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

if __name__ != "__main__":
    logger.info("Starting BotClusters...")
