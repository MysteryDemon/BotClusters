import os
import logging
from app import create_app, socketio

SUPERVISOR_LOG_DIR = "/var/log/supervisor"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = create_app()

if __name__ == "__main__":
    try:
        os.makedirs(SUPERVISOR_LOG_DIR, exist_ok=True)
        port = int(os.environ.get("PORT", 5000))
        socketio.run(
            app,
            host="0.0.0.0",
            port=port,
            debug=True,    
            use_reloader=False
        )

    except Exception as e:
        logger.error(f"Failed to start application: {str(e)}", exc_info=True)
        raise
