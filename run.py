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

if __name__ == "__main__":
    try:
        port = int(os.environ.get("PORT", 5000))
        socketio.run(app, host="0.0.0.0", port=port, debug=True, use_reloader=False)
    except Exception as e:
        logger.error(f"Failed to start application: {str(e)}", exc_info=True)
        raise
